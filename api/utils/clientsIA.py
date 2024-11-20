import os
import json
import logging
import base64
import tempfile
import time

from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Importações atualizadas
from openai import OpenAI
import google.generativeai as genai
import anthropic

from django.conf import settings
from api.exceptions import FileProcessingError, APICommunicationError, MissingAPIKeyError

from django.template import engines

# Importando o client do Document AI
from google.cloud import documentai_v1 as documentai
from ai_config.models import DocumentAIConfiguration

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
    try:
        doc_ai_config = DocumentAIConfiguration.objects.first()
        if not doc_ai_config:
            raise FileProcessingError("Configuração do DocumentAI não encontrada.")
        project_id = doc_ai_config.project_id
        location = doc_ai_config.location
        processor_id = doc_ai_config.processor_id
    except Exception as e:
        logger.error(f"Erro ao obter DocumentAIConfiguration: {e}")
        raise FileProcessingError(f"Erro ao obter DocumentAIConfiguration: {e}")

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
    name = ''
    can_train = False 
    def __init__(self, api_key: str = None, model_name: str = None, configurations: dict = None, base_instruction: str = None, prompt: str = None, responses: str = None):
        self.api_key = api_key
        self.model_name = model_name
        self.configurations = configurations or {}
        self.base_instruction = base_instruction or ""
        self.prompt = prompt or ""
        self.responses = responses or ""
        logger.debug(f"{self.__class__.__name__} inicializado com configurações: {self.configurations}")

    def _render_template(self, template: str, context: dict):
        """
        Carrega o prompt de um arquivo de template e renderiza com o contexto fornecido.
        """
        # Obtenha a engine de templates padrão do Django
        django_engine = engines['django']

        # Crie um template a partir da string
        template_engine = django_engine.from_string(template)

        # Renderize o template com o contexto
        return template_engine.render(context)


    def _prepare_prompts(self, **kwargs) -> dict:
        """
        Prepara os prompts para as IAs com base no tipo de comparação.
        """
        kwargs['ai_name'] = self.name
        kwargs['answer_format'] = self.responses
        base_instruction = self._render_template(self.base_instruction, kwargs)
        prompt = self._render_template(self.prompt, kwargs)
        return {
            'base_instruction': base_instruction,
            'user_prompt': prompt
        }

    def compare(self, data: dict) -> tuple:
        """
        Método unificado para realizar comparações com base no tipo fornecido.
        """
        prompts = self._prepare_prompts(**data)
        response = self._call_api(prompts)
        system_message = prompts.get('base_instruction', '')
        user_message = prompts.get('user_prompt', '')
        return (response, system_message, user_message)

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
    can_train = True
    def __init__(self, api_key=None, model_name=None, configurations=None, base_instruction=None, prompt=None, responses=None):
        if not api_key:
            logger.error("Chave de API para ChatGPT não configurada.")
            raise MissingAPIKeyError("Chave de API para ChatGPT não configurada.")
        super().__init__(api_key, model_name, configurations, base_instruction, prompt, responses)
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

    def train(self, training_file, parameters={}):
        """
        Implementa o treinamento para o ChatGPT.
        """        
        temp_file_path = None  # Inicializa a variável para garantir que exista no finally
        try:
            # Ler o conteúdo JSON do arquivo de treinamento
            with training_file.open('r') as f:
                training_data = json.load(f)
            
            # Certifique-se de que training_data é uma lista de exemplos
            if not isinstance(training_data, list):
                raise ValueError("O arquivo de treinamento deve conter uma lista de exemplos.")
            
            # Converter para JSONL no formato desejado
            jsonl_content = "\n".join([
                json.dumps({
                    "messages": [
                        {"role": "system", "content": example.get("system_message", "")},
                        {"role": "user", "content": example.get("user_message", "")},
                        {"role": "assistant", "content": example.get("response", "")}
                    ]
                }) 
                for example in training_data
            ])
            
            # Salvar o conteúdo JSONL em um arquivo temporário
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl') as temp_file:
                temp_file.write(jsonl_content)
                temp_file_path = temp_file.name
            
            # Criar o arquivo de treinamento via API
            with open(temp_file_path, 'rb') as f:
                ai_training_file = self.client.files.create(
                    file=f,
                    purpose='fine-tune'
                )
            
            # Criar o trabalho de fine-tuning
            fine_tuning_job = self.client.fine_tuning.jobs.create(
                training_file=ai_training_file.id,
                model=self.model_name,
                hyperparameters=parameters
            )

            # Loop para verificar o status do ajuste fino
            while True:
                # Recupere o status atual do trabalho
                status = self.client.fine_tuning.jobs.retrieve(fine_tuning_job.id)
                status_state = status.status

                # Verifique se o trabalho foi concluído
                if status_state == 'succeeded':
                    logger.debug("Modelo treinado")
                    return status.fine_tuned_model
                elif status_state == 'failed':
                    raise APICommunicationError(f"{status.error}")
                else:
                    time.sleep(5)

        except Exception as e:
            logger.error(f"Erro ao treinar modelo com ChatGPT: {e}")
            raise APICommunicationError(f"Erro ao treinar modelo com ChatGPT: {e}")

@register_ai_client
class GeminiClient(APIClient):
    """
    Cliente para interação com a API do Gemini.
    """
    name = "Gemini"
    can_train = True
    def __init__(self, api_key=None, model_name=None, configurations=None, base_instruction=None, prompt=None, responses=None):
        if not api_key:
            logger.error("Chave de API para Gemini não configurada.")
            raise MissingAPIKeyError("Chave de API para Gemini não configurada.")
        super().__init__(api_key, model_name, configurations, base_instruction, prompt, responses)
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

            m = model.generate_content(prompt, generation_config=gemini_config, tools='google_search_retrieval')
            logger.debug("Conteúdo gerado com sucesso.")

            # Utiliza o método parsearHTML
            return parsearHTML(m.text)
        except Exception as e:
            logger.error(f"Erro ao comunicar com a API Gemini: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API Gemini: {e}")

    def train(self, training_content: str) -> str:
        """
        Treina o modelo com o conteúdo fornecido.
        """
        try:
            # Implementação fictícia de treinamento.
            # Substitua este bloco com a lógica real de treinamento da API do Gemini.
            logger.debug("Iniciando treinamento do Gemini.")
            
            # Exemplo: Supondo que a API permita o fine-tuning via um endpoint específico
            # Aqui, apenas simulamos o treinamento e retornamos um nome de modelo fictício.
            trained_model_name = f"{self.model_name}_trained_v1"
            logger.debug(f"Treinamento concluído. Modelo treinado: {trained_model_name}")
            return trained_model_name
        except Exception as e:
            logger.error(f"Erro ao treinar o modelo Gemini: {e}")
            raise APICommunicationError(f"Erro ao treinar o modelo Gemini: {e}")

@register_ai_client
class Claude3Client(APIClient):
    """
    Cliente para interação com a API do Claude 3.
    """
    name = "Claude3"
    can_train = False
    def __init__(self, api_key=None, model_name=None, configurations=None, base_instruction=None, prompt=None, responses=None):
        if not api_key:
            logger.error("Chave de API para Claude 3 não configurada.")
            raise MissingAPIKeyError("Chave de API para Claude 3 não configurada.")
        super().__init__(api_key, model_name, configurations, base_instruction, prompt, responses)
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

    def train(self, training_content: str) -> str:
        """
        Treina o modelo com o conteúdo fornecido.
        """
        try:
            # Implementação fictícia de treinamento.
            # Substitua este bloco com a lógica real de treinamento da API do Claude 3.
            logger.debug("Iniciando treinamento do Claude 3.")
            
            # Exemplo: Supondo que a API permita o fine-tuning via um endpoint específico
            # Aqui, apenas simulamos o treinamento e retornamos um nome de modelo fictício.
            trained_model_name = f"{self.model_name}_trained_v1"
            logger.debug(f"Treinamento concluído. Modelo treinado: {trained_model_name}")
            return trained_model_name
        except Exception as e:
            logger.error(f"Erro ao treinar o modelo Claude 3: {e}")
            raise APICommunicationError(f"Erro ao treinar o modelo Claude 3: {e}")