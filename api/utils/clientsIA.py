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

def extract_text(data: dict) -> str:
    """
    Extrai o texto da instrução a partir dos dados fornecidos.
    """
    if data is not None:
        name = data.get('name')
        content = data.get('content')

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


class APIClient:
    """
    Classe base para clientes de API.
    """
    def __init__(self, api_key: str = None, model_name: str = None, configurations: dict = None):
        self.api_key = api_key
        self.model_name = model_name
        self.configurations = configurations or {}
        logger.debug(f"{self.__class__.__name__} inicializado com configurações: {self.configurations}")

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

    def _prepare_prompts(self, **kwargs) -> dict:
        """
        Prepara os prompts para as IAs com base no tipo de comparação.
        """
        answer_format = self._prepare_answer_format()
        base_instruction = self._load_prompt('base_instruction', {'answer_format': answer_format})


        instructor = kwargs.get('instructor')
        instruction = instructor.get('instruction')
        lab = instructor.get('lab')

        prompt = ''

        if instruction:
            prompt = prompt + self._load_prompt('instructor_instruction', {'instruction': instruction})
            
        if lab:
            prompt = prompt + self._load_prompt('instructor_lab', {'config': lab['config'], 'network' : lab['network']})

        student = kwargs.get('student')
        answers = student.get('answers')
        lab = student.get('lab')

        if answers:
            prompt = prompt + self._load_prompt('student_answers', {'answers': answers})
        
        if lab:
            prompt = prompt + self._load_prompt('student_lab', {'config': lab['config'], 'network' : lab['network']})

        return {
            'base_instruction': base_instruction,
            'user_prompt': prompt
        }

    def compare(self, data: dict) -> str:
        """
        Método unificado para realizar comparações com base no tipo fornecido.
        """
        prompts = self._prepare_prompts(**data)
        response = self._call_api(prompts)
        return response

    def _call_api(self, prompts: dict) -> str:
        """
        Método abstrato para chamar a API específica. Deve ser implementado pelas subclasses.
        """
        raise NotImplementedError("Subclasses devem implementar o método _call_api.")


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

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API do ChatGPT.
        """
        try:
            system_messages = [
                {
                    "role": "system", 
                    "content": prompts['base_instruction']
                },
                {
                    "role": "user", 
                    "content": prompts['user_prompt']
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

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API do Gemini.
        """
        try:
            prompt = prompts['user_prompt']
            system = prompts['base_instruction']

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

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API do Claude 3.
        """
        try:
            system = prompts['base_instruction']
            user_prompt = prompts['user_prompt']

            messages = [
                {
                    "role": "user",
                    "content": user_prompt
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
