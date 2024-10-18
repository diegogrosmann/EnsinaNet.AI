import os
import json
import logging
import base64
import tempfile

from dotenv import load_dotenv
from bs4 import BeautifulSoup

from openai import OpenAI
import google.generativeai as genai

from django.conf import settings
from api.exceptions import FileProcessingError, APICommunicationError

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
    def __init__(self, api_key: str = None, configurations: dict = None):
        self.api_key = api_key
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

    def _prepare_prompts(self, prompt_type: str, **kwargs) -> dict:
        """
        Prepara os prompts para as IAs com base no tipo de comparação.
        """
        answer_format = self._prepare_answer_format()
        base_instruction = f"""
            Você deve atuar como um professor de Redes de Computadores.
            Você deve ter uma linguagem técnica e objetiva.
            A resposta deve ser estruturada da seguinte forma:
            {answer_format}
            A resposta deve ser formatada em HTML. Toda a resposta deve estar dentro da tag <div>.
        """

        if prompt_type == 'compare_labs':
            instructor_config = kwargs.get('instructor_config')
            instructor_network = kwargs.get('instructor_network')
            student_config = kwargs.get('student_config')
            student_network = kwargs.get('student_network')

            user_prompt = f"""
                Você vai receber quatro informações: as configurações corretas dos equipamentos, as conexões da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
                Você deve comparar as configurações corretas com as que eu fiz. Com base nos erros que cometi, você deve propor conteúdos para serem estudados.

                Configuração Correta:
                {instructor_config}

                Rede Correta:
                {instructor_network}

                Minha Configuração:
                {student_config}

                Minha Rede:
                {student_network}

                Analise as configurações, identifique os erros e proponha conteúdos para estudar.
            """
        elif prompt_type == 'compare_instruction':
            instruction_text = kwargs.get('instruction_text')
            student_config = kwargs.get('student_config')
            student_network = kwargs.get('student_network')

            user_prompt = f"""
                Você vai receber três informações: as instruções de configuração, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
                Você deve comparar as instruções com as configurações que eu fiz. Você deve analisar as minhas configurações, identificar erros e propor conteúdos para serem estudados.

                Instruções:
                {instruction_text}

                Minha Configuração:
                {student_config}

                Minha Rede:
                {student_network}

                Analise as configurações, identifique os erros e proponha conteúdos para estudar.
            """
        elif prompt_type == 'compare_instruction_only':
            instruction_text = kwargs.get('instruction_text')

            user_prompt = f"""
                Você vai receber uma informação: as instruções de configuração com minhas respostas.
                Você deve analisar minhas respostas, identificar erros e propor conteúdos para serem estudados.

                Instruções com Respostas:
                {instruction_text}

                Analise as respostas, identifique os erros e proponha conteúdos para estudar.
            """
        elif prompt_type == 'compare_complete':
            instruction_text = kwargs.get('instruction_text')
            instructor_config = kwargs.get('instructor_config')
            instructor_network = kwargs.get('instructor_network')
            student_config = kwargs.get('student_config')
            student_network = kwargs.get('student_network')

            user_prompt = f"""
                Você vai receber cinco informações: as instruções de configuração, as configurações corretas dos equipamentos, as conexões corretas da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
                Você deve comparar todas as informações fornecidas. Analise as instruções, as configurações corretas e as configurações realizadas, identifique erros, e proponha conteúdos para serem estudados.

                Instruções:
                {instruction_text}

                Configuração Correta:
                {instructor_config}

                Rede Correta:
                {instructor_network}

                Minha Configuração:
                {student_config}

                Minha Rede:
                {student_network}

                Analise todas as informações, identifique os erros e proponha conteúdos para estudar.
            """
        else:
            logger.error(f"Tipo de prompt desconhecido: {prompt_type}")
            raise ValueError(f"Tipo de prompt desconhecido: {prompt_type}")

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

    def __init__(self, configurations=None):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY não está definido nas variáveis de ambiente.")
            raise APICommunicationError("OPENAI_API_KEY não está definido nas variáveis de ambiente.")
        super().__init__(api_key, configurations)
        self.client = OpenAI(api_key=self.api_key)
        logger.debug("ChatGPTClient inicializado.")

    def compare(self, prompt_data: dict) -> str:
        """
        Realiza a comparação usando o ChatGPT.
        """
        try:
            system_messages = [
                {"role": "system", "content": prompt_data['base_instruction']},
                {"role": "user", "content": prompt_data['user_prompt']}
            ]

            self.configurations['model'] = self.configurations.get('model-name', 'gpt-4')
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

    def __init__(self, configurations=None):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY não está definido nas variáveis de ambiente.")
            raise APICommunicationError("GEMINI_API_KEY não está definido nas variáveis de ambiente.")
        super().__init__(api_key, configurations)
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
            prompt=prompt_data['user_prompt'],
            system=prompt_data['base_instruction']

            if 'model-name' in self.configurations:
                _model_name = self.configurations.get('model-name')
                self.configurations.pop('model-name')
            else:
                _model_name = "gemini-1.5-pro"

            logger.debug("Iniciando comparação com Gemini.")
            
            model = genai.GenerativeModel(
                model_name=_model_name, 
                system_instruction=system
            )   

            logger.debug("Modelo Gemini configurado.")

            gemini_config = genai.types.GenerationConfig(
                **self.configurations
            )
            logger.debug("Configuração de geração definida.")

            inputs = [prompt]

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
