import os
import json
import logging
import base64
import tempfile

from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Importações atualizadas
from openai import OpenAI
import google.generativeai as genai
import anthropic

from django.conf import settings
from api.exceptions import FileProcessingError, APICommunicationError, MissingAPIKeyError

# Importando o client do Document AI
from google.cloud import documentai_v1 as documentai

# Configuração do logger
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Registry para armazenar os clientes de IA disponíveis
AVAILABLE_AI_CLIENTS = []


def register_ai_client(cls):
    """
    Decorador para registrar uma classe de cliente de IA no registry.
    """
    AVAILABLE_AI_CLIENTS.append(cls)
    return cls


def parsearHTML(html: str) -> str:
    """
    Parseia o HTML fornecido e retorna a div mais externa.
    """
    try:
        logger.debug("Iniciando o parseamento do HTML.")
        soup = BeautifulSoup(html, 'html.parser')
        outer_div = soup.find('div')
        if outer_div:
            logger.debug("Div externa encontrada no HTML.")
            return str(outer_div)
        else:
            logger.warning("Nenhuma div encontrada no HTML. Retornando o HTML original.")
            return html
    except Exception as e:
        logger.error(f"Erro ao parsear o HTML: {e}")
        raise ValueError(f"Erro ao parsear o HTML: {e}")


def processar_documento(conteudo_documento: bytes, nome_documento: str) -> str:
    """
    Processa o documento usando o Google Cloud Document AI e retorna o texto extraído.
    """
    logger.debug(f"Iniciando o processamento do documento: {nome_documento}")

     # Configurações do Document AI
    project_id = 'doutorado2' 
    location = 'us'
    processor_id = 'f336c42ad14e194a'

    try:
        # Instanciar o cliente
        client = documentai.DocumentProcessorServiceClient()

        # Construir o caminho do processador
        nome_processador = client.processor_path(project_id, location, processor_id)

        # Determinar o tipo MIME com base na extensão do arquivo
        _, ext = os.path.splitext(nome_documento)
        ext = ext.lower()
        if ext == '.pdf':
            mime_type = 'application/pdf'
        elif ext in ['.png', '.jpg', '.jpeg']:
            mime_type = f'image/{ext[1:]}'
        else:
            mime_type = 'application/octet-stream'  # Tipo genérico

        # Criar um arquivo temporário para armazenar o conteúdo
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
            temp_file.write(conteudo_documento)
            temp_file_path = temp_file.name

        logger.info(f"Arquivo temporário criado: {temp_file_path}")

        # Ler o conteúdo do documento
        with open(temp_file_path, "rb") as f:
            conteudo_documento = f.read()

        # Criar a solicitação de processamento
        request = documentai.ProcessRequest(
            name=nome_processador,
            raw_document=documentai.RawDocument(content=conteudo_documento, mime_type=mime_type)
        )

        # Processar o documento
        resposta = client.process_document(request=request)
        texto_extraido = resposta.document.text
        logger.debug("Documento processado com sucesso.")

        # Remover o arquivo temporário
        os.remove(temp_file_path)
        logger.info(f"Arquivo temporário removido: {temp_file_path}")

        return texto_extraido

    except Exception as e:
        logger.error(f"Erro ao processar o documento {nome_documento}: {e}")
        raise FileProcessingError(f"Erro ao processar o documento: {e}")


class APIClient:
    """
    Classe base para clientes de API.
    """
    def __init__(self, api_key: str = None, model_name: str = None, configurations: dict = None):
        self.api_key = api_key
        self.model_name = model_name
        self.configurations = configurations or {}
        logger.debug(f"{self.__class__.__name__} inicializado com configurações: {self.configurations}")

    def extract_instruction_text(self, instruction_data: dict) -> str:
        """
        Extrai o texto da instrução a partir dos dados fornecidos.
        """
        if instruction_data is not None:
            name = instruction_data.get('name')
            content = instruction_data.get('content')

            if not name or not content:
                logger.error("Dados de instrução incompletos.")
                raise FileProcessingError("Dados de instrução incompletos.")

            try:
                # Decodifica o conteúdo do arquivo em Base64
                instruction_decoded = base64.b64decode(content)
                logger.debug("Conteúdo do arquivo decodificado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao decodificar o conteúdo do arquivo: {e}")
                raise FileProcessingError(f"Erro ao decodificar o conteúdo do arquivo: {e}")

            try:
                # Processa o documento e extrai o texto
                instruction_text = processar_documento(instruction_decoded, name)
                logger.info("Texto da instrução extraído com sucesso.")
                return instruction_text
            except Exception as e:
                logger.error(f"Erro ao processar o documento: {e}")
                raise FileProcessingError(f"Erro ao processar o documento: {e}")

        else:
            logger.error("Nenhum dado de instrução fornecido.")
            raise FileProcessingError("Nenhum dado de instrução fornecido.")

    def _prepare_answer_format(self) -> str:
        """
        Prepara o formato da resposta carregando um arquivo HTML.
        """
        file_path = os.path.join(settings.BASE_DIR, 'api', 'templates', 'resposta.html')
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            logger.debug("Formato de resposta carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao ler o arquivo de formato de resposta: {e}")
            raise FileProcessingError(f"Erro ao ler o arquivo de formato de resposta: {e}")
        return content

    def _load_prompt(self, prompt_name, context=None):
        """
        Carrega o prompt de um arquivo de template e renderiza com o contexto fornecido.
        """
        from django.template.loader import render_to_string
        template_name = f'api/prompts/{prompt_name}.txt'
        return render_to_string(template_name, context or {})

    def _prepare_prompts(self, prompt_type: str, **kwargs) -> dict:
        """
        Prepara os prompts para as IAs com base no tipo de comparação.
        """
        answer_format = self._prepare_answer_format()
        base_instruction = self._load_prompt('base_instruction', {'answer_format': answer_format})

        user_prompt = self._load_prompt(prompt_type, kwargs)

        return {
            'base_instruction': base_instruction,
            'user_prompt': user_prompt
        }


@register_ai_client
class ChatGPTClient(APIClient):
    """
    Cliente para interação com a API do ChatGPT.
    """
    name = "ChatGPT"

    def __init__(self, api_key=None, model_name=None, configurations=None):
        if not api_key:
            logger.error("Chave de API para ChatGPT não configurada.")
            raise MissingAPIKeyError("Chave de API para ChatGPT não configurada.")
        super().__init__(api_key, model_name, configurations)
        self.client = OpenAI(api_key=self.api_key)
        logger.debug("ChatGPTClient inicializado.")

    def compare(self, prompt_data: dict) -> str:
        """
        Realiza a comparação usando o ChatGPT.
        """
        try:
            system_messages = [
                {
                    "role": "system", 
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_data['base_instruction']
                        }
                    ]
                },
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_data['user_prompt']
                        }
                    ]
                }
            ]

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = system_messages

            response = self.client.chat.completions.create(**self.configurations)

            logger.debug("Chat criado e concluído com sucesso.")

            if not response:
                logger.error("Nenhuma mensagem retornada pelo ChatGPT.")
                raise APICommunicationError("Nenhuma mensagem retornada pelo ChatGPT.")

            return parsearHTML(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Erro ao comunicar com a API ChatGPT: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API ChatGPT: {e}")

    def compare_labs(self, data: dict) -> dict:
        """
        Implementação do método compare_labs para o ChatGPTClient.
        """
        try:
            instructor_config = json.dumps(data['instructor']['config'], indent=4)
            instructor_network = json.dumps(data['instructor']['network'], indent=4)
            student_config = json.dumps(data['student']['config'], indent=4)
            student_network = json.dumps(data['student']['network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        prompt_data = self._prepare_prompts(
            'compare_labs',
            instructor_config=instructor_config,
            instructor_network=instructor_network,
            student_config=student_config,
            student_network=student_network
        )

        comparison_result = self.compare(prompt_data)
        return {"response": comparison_result}

    def compare_instruction(self, data: dict) -> dict:
        """
        Implementação do método compare_instruction para o ChatGPTClient.
        """
        try:
            instruction_text = self.extract_instruction_text(data['instruction'])
            has_answers = data['instruction'].get('has_answers', False)

            if 'student' in data:
                student_config = json.dumps(data['student']['config'], indent=4)
                student_network = json.dumps(data['student']['network'], indent=4)
                prompt_type = 'compare_instruction'
                prompt_data = self._prepare_prompts(
                    prompt_type,
                    instruction_text=instruction_text,
                    student_config=student_config,
                    student_network=student_network
                )
            elif has_answers:
                prompt_type = 'compare_instruction_only'
                prompt_data = self._prepare_prompts(
                    prompt_type,
                    instruction_text=instruction_text
                )
            else:
                logger.error("Dados insuficientes para comparação.")
                raise FileProcessingError("Dados insuficientes para comparação.")

            comparison_result = self.compare(prompt_data)
            return {"response": comparison_result}

        except Exception as e:
            logger.error(f"Erro em compare_instruction: {e}")
            raise

    def compare_complete(self, data: dict) -> dict:
        """
        Implementação do método compare_complete para o ChatGPTClient.
        """
        try:
            instruction_text = self.extract_instruction_text(data['instruction'])
            instructor_config = json.dumps(data['instructor']['config'], indent=4)
            instructor_network = json.dumps(data['instructor']['network'], indent=4)
            student_config = json.dumps(data['student']['config'], indent=4)
            student_network = json.dumps(data['student']['network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados de entrada: {e}")
            raise FileProcessingError(f"Erro ao processar dados de entrada: {e}")

        prompt_data = self._prepare_prompts(
            'compare_complete',
            instruction_text=instruction_text,
            instructor_config=instructor_config,
            instructor_network=instructor_network,
            student_config=student_config,
            student_network=student_network
        )

        comparison_result = self.compare(prompt_data)
        return {"response": comparison_result}


@register_ai_client
class GeminiClient(APIClient):
    """
    Cliente para interação com a API do Gemini.
    """
    name = "Gemini"

    def __init__(self, api_key=None, model_name=None, configurations=None):
        if not api_key:
            logger.error("Chave de API para Gemini não configurada.")
            raise MissingAPIKeyError("Chave de API para Gemini não configurada.")
        super().__init__(api_key, model_name, configurations)
        genai.configure(api_key=self.api_key)
        logger.debug("GeminiClient inicializado.")

    def compare(self, prompt_data: dict) -> str:
        """
        Realiza a comparação usando o Gemini.

        :param instruction: Instruções do sistema.
        :param prompt: Prompt para geração de conteúdo.
        :param instruction_file_path: Caminho para o arquivo de instruções (opcional).
        :return: Resposta gerada pelo Gemini.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do Gemini.
        """
        try:
            prompt = prompt_data['user_prompt']
            system = prompt_data['base_instruction']

            logger.debug("Iniciando comparação com Gemini.")

            gemini_config = genai.types.GenerationConfig(
                **self.configurations
            )
            logger.debug("Modelo Gemini configurado.")

            model = genai.GenerativeModel(
                model_name=self.model_name, 
                system_instruction=system
            )
            logger.debug("Configuração de geração definida.")

            m = model.generate_content(prompt, generation_config=gemini_config)
            logger.debug("Conteúdo gerado com sucesso.")

            # Utiliza o método parsearHTML
            return parsearHTML(m.text)
        except Exception as e:
            logger.error(f"Erro ao comunicar com a API Gemini: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API Gemini: {e}")

    def compare_labs(self, data: dict) -> dict:
        """
        Implementação do método compare_labs para o GeminiClient.
        """
        try:
            instructor_config = json.dumps(data['instructor']['config'], indent=4)
            instructor_network = json.dumps(data['instructor']['network'], indent=4)
            student_config = json.dumps(data['student']['config'], indent=4)
            student_network = json.dumps(data['student']['network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        prompt_data = self._prepare_prompts(
            'compare_labs',
            instructor_config=instructor_config,
            instructor_network=instructor_network,
            student_config=student_config,
            student_network=student_network
        )

        comparison_result = self.compare(prompt_data)
        return {"response": comparison_result}

    def compare_instruction(self, data: dict) -> dict:
        """
        Implementação do método compare_instruction para o GeminiClient.
        """
        try:
            instruction_text = self.extract_instruction_text(data['instruction'])
            has_answers = data['instruction'].get('has_answers', False)

            if 'student' in data:
                student_config = json.dumps(data['student']['config'], indent=4)
                student_network = json.dumps(data['student']['network'], indent=4)
                prompt_type = 'compare_instruction'
                prompt_data = self._prepare_prompts(
                    prompt_type,
                    instruction_text=instruction_text,
                    student_config=student_config,
                    student_network=student_network
                )
            elif has_answers:
                prompt_type = 'compare_instruction_only'
                prompt_data = self._prepare_prompts(
                    prompt_type,
                    instruction_text=instruction_text
                )
            else:
                logger.error("Dados insuficientes para comparação.")
                raise FileProcessingError("Dados insuficientes para comparação.")

            comparison_result = self.compare(prompt_data)
            return {"response": comparison_result}

        except Exception as e:
            logger.error(f"Erro em compare_instruction: {e}")
            raise

    def compare_complete(self, data: dict) -> dict:
        """
        Implementação do método compare_complete para o GeminiClient.
        """
        try:
            instruction_text = self.extract_instruction_text(data['instruction'])
            instructor_config = json.dumps(data['instructor']['config'], indent=4)
            instructor_network = json.dumps(data['instructor']['network'], indent=4)
            student_config = json.dumps(data['student']['config'], indent=4)
            student_network = json.dumps(data['student']['network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados de entrada: {e}")
            raise FileProcessingError(f"Erro ao processar dados de entrada: {e}")

        prompt_data = self._prepare_prompts(
            'compare_complete',
            instruction_text=instruction_text,
            instructor_config=instructor_config,
            instructor_network=instructor_network,
            student_config=student_config,
            student_network=student_network
        )

        comparison_result = self.compare(prompt_data)
        return {"response":comparison_result}

@register_ai_client
class Claude3Client(APIClient):
    """
    Cliente para interação com a API do Claude 3.
    """
    name = "Claude3"

    def __init__(self, api_key=None, model_name=None, configurations=None):
        if not api_key:
            logger.error("Chave de API para Claude 3 não configurada.")
            raise MissingAPIKeyError("Chave de API para Claude 3 não configurada.")
        super().__init__(api_key, model_name, configurations)
        self.client = anthropic.Anthropic(api_key=self.api_key)
        logger.debug("Claude3Client inicializado.")

    def compare(self, prompt_data: dict) -> str:
        """
        Realiza a comparação usando o Claude 3.
        """
        try:
            system = prompt_data['base_instruction']
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_data['user_prompt']
                        }
                    ]
                }
            ]

            self.configurations['model'] = self.model_name
            self.configurations['system'] = system
            self.configurations['messages'] = messages
            self.configurations['max_tokens'] = self.configurations.get('max_tokens', 1024)

            response = self.client.messages.create(
                **self.configurations
            )

            logger.debug("Mensagem enviada e resposta recebida com sucesso.")

            if not response or not response.content or not response.content[0].text:
                logger.error("Nenhuma mensagem retornada pelo Claude 3.")
                raise APICommunicationError("Nenhuma mensagem retornada pelo Claude 3.")

            return parsearHTML(response.content[0].text)

        except Exception as e:
            logger.error(f"Erro ao comunicar com a API do Claude 3: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API do Claude 3: {e}")

    def compare_labs(self, data: dict) -> dict:
        """
        Implementação do método compare_labs para o Claude3Client.
        """
        try:
            instructor_config = json.dumps(data['instructor']['config'], indent=4)
            instructor_network = json.dumps(data['instructor']['network'], indent=4)
            student_config = json.dumps(data['student']['config'], indent=4)
            student_network = json.dumps(data['student']['network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        prompt_data = self._prepare_prompts(
            'compare_labs',
            instructor_config=instructor_config,
            instructor_network=instructor_network,
            student_config=student_config,
            student_network=student_network
        )

        comparison_result = self.compare(prompt_data)
        return {"response": comparison_result}

    def compare_instruction(self, data: dict) -> dict:
        """
        Implementação do método compare_instruction para o Claude3Client.
        """
        try:
            instruction_text = self.extract_instruction_text(data['instruction'])
            has_answers = data['instruction'].get('has_answers', False)

            if 'student' in data:
                student_config = json.dumps(data['student']['config'], indent=4)
                student_network = json.dumps(data['student']['network'], indent=4)
                prompt_type = 'compare_instruction'
                prompt_data = self._prepare_prompts(
                    prompt_type,
                    instruction_text=instruction_text,
                    student_config=student_config,
                    student_network=student_network
                )
            elif has_answers:
                prompt_type = 'compare_instruction_only'
                prompt_data = self._prepare_prompts(
                    prompt_type,
                    instruction_text=instruction_text
                )
            else:
                logger.error("Dados insuficientes para comparação.")
                raise FileProcessingError("Dados insuficientes para comparação.")

            comparison_result = self.compare(prompt_data)
            return {"response": comparison_result}

        except Exception as e:
            logger.error(f"Erro em compare_instruction: {e}")
            raise

    def compare_complete(self, data: dict) -> dict:
        """
        Implementação do método compare_complete para o Claude3Client.
        """
        try:
            instruction_text = self.extract_instruction_text(data['instruction'])
            instructor_config = json.dumps(data['instructor']['config'], indent=4)
            instructor_network = json.dumps(data['instructor']['network'], indent=4)
            student_config = json.dumps(data['student']['config'], indent=4)
            student_network = json.dumps(data['student']['network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados de entrada: {e}")
            raise FileProcessingError(f"Erro ao processar dados de entrada: {e}")

        prompt_data = self._prepare_prompts(
            'compare_complete',
            instruction_text=instruction_text,
            instructor_config=instructor_config,
            instructor_network=instructor_network,
            student_config=student_config,
            student_network=student_network
        )

        comparison_result = self.compare(prompt_data)
        return {"response": comparison_result}