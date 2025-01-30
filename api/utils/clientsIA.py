"""
Este módulo fornece utilitários e clientes para interagir com diferentes APIs de IA,
incluindo OpenAI, Google Gemini, Anthropic Claude 3 e Perplexity. Ele facilita o processamento
de documentos, extração de texto e comunicação com os serviços de IA configurados.
"""
import os
import json
import logging
import base64
import tempfile
import time
import html
import requests
import markdown

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


def parsear_html(html: str) -> str:
    """Parseia o HTML fornecido e retorna a div mais externa.

    Args:
        html (str): String contendo o HTML a ser parseado.

    Returns:
        str: HTML da div mais externa ou HTML original se nenhuma div for encontrada.

    Raises:
        ValueError: Se ocorrer um erro durante o parse do HTML.
    """
    function_name = 'parsearHTML'
    try:
        logger.debug(f"{function_name}: Iniciando o parseamento do HTML.")
        soup = BeautifulSoup(html, 'html.parser')
        outer_div = soup.find('div')
        if (outer_div):
            logger.debug(f"{function_name}: Div externa encontrada no HTML.")
            return str(outer_div)
        else:
            logger.warning(f"{function_name}: Nenhuma div encontrada no HTML. Retornando o HTML original.")
            return html
    except Exception as e:
        logger.error(f"{function_name}: Erro ao parsear o HTML: {e}")
        raise ValueError(f"Erro ao parsear o HTML: {e}")


def processar_documento(conteudo_documento: bytes, nome_documento: str) -> str:
    """Processa um documento usando o Google Cloud Document AI.

    Args:
        conteudo_documento (bytes): Conteúdo do documento em bytes.
        nome_documento (str): Nome do arquivo do documento.

    Returns:
        str: Texto extraído do documento.

    Raises:
        FileProcessingError: Se ocorrer um erro no processamento do documento.
    """
    function_name = 'processar_documento'
    logger.debug(f"{function_name}: Iniciando o processamento do documento: {nome_documento}")

    # Configurações do Document AI
    try:
        doc_ai_config = DocumentAIConfiguration.objects.first()
        if not doc_ai_config:
            raise FileProcessingError("Configuração do DocumentAI não encontrada.")
        project_id = doc_ai_config.project_id
        location = doc_ai_config.location
        processor_id = doc_ai_config.processor_id
    except Exception as e:
        logger.error(f"{function_name}: Erro ao obter DocumentAIConfiguration: {e}")
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

        logger.info(f"{function_name}: Arquivo temporário criado: {temp_file_path}")

        try:
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
            logger.debug(f"{function_name}: Documento processado com sucesso.")

            return texto_extraido

        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"{function_name}: Arquivo temporário removido: {temp_file_path}")

    except FileProcessingError as e:
        logger.error(f"{function_name}: Erro específico ao processar o documento {nome_documento}: {e}")
        raise
    except Exception as e:
        logger.error(f"{function_name}: Erro inesperado: {e}")
        raise FileProcessingError("Erro inesperado ao processar o documento.")


def extract_text(data: dict) -> str:
    """Extrai texto de um documento fornecido em formato base64.

    Args:
        data (dict): Dicionário contendo 'name' e 'content' em base64.

    Returns:
        str: Texto extraído do documento.

    Raises:
        FileProcessingError: Se ocorrer erro na extração ou processamento.
    """
    function_name = 'extract_text'
    if data is not None:
        name = data.get('name')
        content = data.get('content')

        if not name or not content:
            logger.error(f"{function_name}: Dados de instrução incompletos.")
            raise FileProcessingError("Dados de instrução incompletos.")

        try:
            # Decodifica o conteúdo do arquivo em Base64
            instruction_decoded = base64.b64decode(content)
            logger.debug(f"{function_name}: Conteúdo do arquivo decodificado com sucesso.")
        except Exception as e:
            logger.error(f"{function_name}: Erro ao decodificar o conteúdo do arquivo: {e}")
            raise FileProcessingError(f"Erro ao decodificar o conteúdo do arquivo: {e}")

        try:
            # Processa o documento e extrai o texto
            instruction_text = processar_documento(instruction_decoded, name)
            logger.info(f"{function_name}: Texto da instrução extraído com sucesso.")
            return instruction_text
        except Exception as e:
            logger.error(f"{function_name}: Erro ao processar o documento: {e}")
            raise FileProcessingError(f"Erro ao processar o documento: {e}")

    else:
        logger.error(f"{function_name}: Nenhum dado de instrução fornecido.")
        raise FileProcessingError("Nenhum dado de instrução fornecido.")


from api.constants import AIClientConfig, ProcessingResult

class APIClient:
    """Classe base abstrata para implementação de clientes de IA."""
    name = ''
    can_train = False
    
    def __init__(self, config: dict):
        self.api_key = config.api_key
        self.model_name = config.model_name
        self.configurations = config.configurations.copy() if config.configurations else {}
        self.base_instruction = config.base_instruction or ""
        self.prompt = config.prompt or ""
        self.responses = config.responses or ""
        self.api_url = config.api_url or ""
        if not self.api_key:
            raise MissingAPIKeyError(f"{self.name}: Chave de API não configurada.")
        logger.debug(f"{self.__class__.__name__}.__init__: Inicializado com configurações: {self.configurations}")

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
        try:
            kwargs['ai_name'] = self.name
            kwargs['answer_format'] = self.responses
            kwargs['can_train'] = self.can_train
            kwargs['train'] = self._prepare_train(**kwargs)
            base_instruction = html.unescape(self._render_template(self.base_instruction, kwargs))
            prompt = html.unescape(self._render_template(self.prompt, kwargs))
            return {
                'base_instruction': base_instruction,
                'user_prompt': prompt
            }
        except Exception as e:
            logger.error(f"{self.__class__.__name__}._prepare_prompts: Nenhuma mensagem retornada.")
            raise APICommunicationError(f"{self.name}: Nenhuma mensagem retornada.")
    
    def _prepare_train(self, **kwargs) -> dict:
        # Prepara os dados de treinamento
        training_file = kwargs.get('training_file')
        training = ''
        if training_file:
            try:
                with training_file.open('r') as f:
                    training_data = json.load(f)
                training_examples = ""
                for example in training_data:
                    system_message = example.get('system_message', '')
                    user_message = example.get('user_message', '')
                    response = example.get('response', '')
                    training_examples += f"Exemplo:\n Mensagem do Usuário {system_message}\n {user_message}\nResposta esperada: {response}\n\n"
                # Adicionar os exemplos ao prompt
                training = f"{training} \n {training_examples}"
            except Exception as e:
                logger.error(f"{self.__class__.__name__}._prepare_train: Erro ao ler o arquivo de treinamento: {e}")
        return training

    def compare(self, data: dict) -> tuple:
        """
        Método unificado para realizar comparações com base no tipo fornecido.
        """
        logger.debug(f"{self.__class__.__name__}.compare: Iniciando comparação.")
        prompts = self._prepare_prompts(**data)
        response = self._call_api(prompts)
        system_message = prompts.get('base_instruction', '')
        user_message = prompts.get('user_prompt', '')
        logger.debug(f"{self.__class__.__name__}.compare: Comparação concluída com sucesso.")
        return (response, system_message, user_message)

    def _call_api(self, prompts: dict) -> str:
        """
        Método abstrato para chamar a API específica. Deve ser implementado pelas subclasses.
        """
        raise NotImplementedError(f"{self.name}: Subclasses devem implementar o método _call_api.")


class ChatGPTClient(APIClient):
    """Cliente para interação com a API do ChatGPT.

    Implementa a interface para comunicação com o modelo GPT da OpenAI,
    incluindo suporte para fine-tuning e geração de respostas.
    """
    name = "ChatGPT"
    can_train = True
    
    def __init__(self, config: AIClientConfig):
        super().__init__(config)
        args = {
            'api_key': self.api_key
        }

        # Verifica se base_url não é nulo e adiciona ao dicionário
        if self.api_url is not None:
            args['base_url'] = self.api_url

        # Cria a instância do cliente OpenAI com os argumentos apropriados
        self.client = OpenAI(**args)

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

            logger.debug(f"{self.__class__.__name__}._call_api: Chat criado e concluído com sucesso.")

            if not response:
                logger.error(f"{self.__class__.__name__}._call_api: Nenhuma mensagem retornada.")
                raise APICommunicationError(f"{self.name}: Nenhuma mensagem retornada.")

            return parsear_html(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"{self.name}: Erro ao comunicar com a API: {e}")

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
                    logger.debug(f"{self.__class__.__name__}.train: Modelo treinado.")
                    return status.fine_tuned_model
                elif status_state == 'failed':
                    raise APICommunicationError(f"{self.name}: {status.error}")
                else:
                    time.sleep(5)

        except Exception as e:
            logger.error(f"{self.__class__.__name__}.train: Erro ao treinar o modelo: {e}")
            raise APICommunicationError(f"{self.name}: Erro ao treinar o modelo: {e}")


class GeminiClient(APIClient):
    """Cliente para interação com a API do Google Gemini.

    Implementa a interface para comunicação com o modelo Gemini do Google,
    incluindo suporte para treinamento e geração de conteúdo.
    """
    name = "Gemini"
    can_train = True
    
    def __init__(self, config: AIClientConfig):
        super().__init__(config)
        genai.configure(api_key=self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API do Gemini.
        """
        try:
            prompt = prompts['user_prompt']
            system = prompts['base_instruction']

            logger.debug(f"{self.__class__.__name__}._call_api: Iniciando comparação.")

            gemini_config = genai.types.GenerationConfig(
                **self.configurations
            )
            logger.debug(f"{self.__class__.__name__}._call_api: Modelo configurado.")

            model = genai.GenerativeModel(
                model_name=self.model_name, 
                system_instruction=system
            )
            logger.debug(f"{self.__class__.__name__}._call_api: Configuração de geração definida.")

            m = model.generate_content(prompt, generation_config=gemini_config)
            logger.debug(f"{self.__class__.__name__}._call_api: Conteúdo gerado com sucesso.")

            # Utiliza o método parsearHTML
            return parsear_html(m.text)
        except Exception as e:
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"{self.name}: Erro ao comunicar com a API: {e}")

    def train(self, training_file, parameters={}):
        """
        Implementa o treinamento para o Gemini.
        """
        try:
            # Ler o conteúdo JSON do arquivo de treinamento
            with training_file.open('r') as f:
                training_data_raw = json.load(f)

            # Preparar os dados de treinamento no formato esperado
            training_data = []
            for example in training_data_raw:
                text_input = example.get('user_message', '')
                output = example.get('response', '')
                training_data.append({'text_input': text_input, 'output': output})

            # Obter os parâmetros de treinamento, usando valores padrão se não fornecidos
            display_name = parameters.get('display_name', 'Fine-tuned Model')
            epoch_count = int(parameters.get('epoch_count', 1))
            batch_size = int(parameters.get('batch_size', 4))
            learning_rate = float(parameters.get('learning_rate', 0.001))
            source_model = "models/"+self.model_name  # Modelo base para fine-tuning

            # Iniciar o treinamento
            operation = genai.create_tuned_model(
                display_name=display_name,
                source_model=source_model,
                epoch_count=epoch_count,
                batch_size=batch_size,
                learning_rate=learning_rate,
                training_data=training_data,
            )
            logger.debug(f"{self.__class__.__name__}.train: Operação de treinamento iniciada com sucesso.")

            # Aguardar a conclusão do treinamento
            while not operation.done():
                logger.debug(f"{self.__class__.__name__}.train: Treinamento em andamento...")
                time.sleep(10)  # Aguarda 10 segundos antes de verificar novamente

            result = operation.result()
            trained_model_name = result.name  # Nome do modelo treinado
            logger.debug(f"{self.__class__.__name__}.train: Treinamento concluído. Modelo treinado: {trained_model_name}")
            return trained_model_name
        except Exception as e:
            logger.error(f"{self.__class__.__name__}.train: Erro ao treinar o modelo: {e}")
            raise APICommunicationError(f"{self.name}: Erro ao treinar o modelo: {e}")


class Claude3Client(APIClient):
    """Cliente para interação com a API do Anthropic Claude 3.

    Implementa a interface para comunicação com o modelo Claude 3,
    focando na geração de respostas precisas.
    """
    name = "Claude3"
    can_train = False
    
    def __init__(self, config: AIClientConfig):
        super().__init__(config)
        self.client = anthropic.Anthropic(api_key=self.api_key)

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

            logger.debug(f"{self.__class__.__name__}._call_api: Mensagem enviada e resposta recebida com sucesso.")

            if not response or not response.content or not response.content[0].text:
                logger.error(f"{self.__class__.__name__}._call_api: Nenhuma mensagem retornada.")
                raise APICommunicationError(f"{self.name}: Nenhuma mensagem retornada.")

            return parsear_html(response.content[0].text)

        except Exception as e:
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"{self.name}: Erro ao comunicar com a API: {e}")


class PerplexityClient(APIClient):
    """Cliente para interação com a API da Perplexity.

    Implementa a interface para comunicação com os modelos da Perplexity,
    fornecendo capacidades de geração de texto.
    """
    name = "Perplexity"
    can_train = False

    def __init__(self, config: AIClientConfig):
        super().__init__(config)

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API da Perplexity.
        """
        try:
            url = "https://api.perplexity.ai/chat/completions"

            # Preparar o payload com os prompts e configurações
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": prompts['base_instruction']
                    },
                    {
                        "role": "user",
                        "content": prompts['user_prompt']
                    }
                ],
            }

            # Atualizar o payload com as configurações adicionais
            if self.configurations:
                payload.update(self.configurations)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.debug(f"{self.__class__.__name__}._call_api: Enviando solicitação para a API.")
            response = requests.post(url, json=payload, headers=headers)

            # Verificar o status da resposta
            if response.status_code != 200:
                logger.error(f"{self.__class__.__name__}._call_api: API retornou o código de status {response.status_code}")
                raise APICommunicationError(f"{self.name}: API retornou o código de status {response.status_code}")

            response_json = response.json()

            # Extrair o texto gerado da resposta
            generated_text = response_json['choices'][0]['message'].get('content', '')

            if not generated_text:
                logger.error(f"{self.__class__.__name__}._call_api: Nenhum texto retornado na resposta.")
                raise APICommunicationError(f"{self.name}: Nenhum texto retornado na resposta.")

            logger.debug(f"{self.__class__.__name__}._call_api: Resposta recebida com sucesso.")

            generated_text = markdown.markdown(generated_text)
            return parsear_html(generated_text)

        except Exception as e:
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"{self.name}: Erro ao comunicar com a API: {e}")

AI_CLIENT_MAPPING = {
    "ChatGPT": ChatGPTClient,
    "Gemini": GeminiClient,
    "Claude3": Claude3Client,
    "Perplexity": PerplexityClient,
}