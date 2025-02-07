"""
Este módulo fornece utilitários e clientes para interagir com diferentes APIs de IA.

Classes:
    APIClient: Classe base para todos os clientes de IA
    ChatGPTClient: Cliente para OpenAI GPT
    GeminiClient: Cliente para Google Gemini
    ...

Funções:
    register_ai_client: Decorador para registro de clientes
"""
import json
import logging
import tempfile
import time
import html
import requests
import ast

from dotenv import load_dotenv

from openai import OpenAI, AzureOpenAI
import google.generativeai as genai
import anthropic
from llamaapi import LlamaAPI
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

from api.exceptions import APICommunicationError, MissingAPIKeyError

from django.template import engines
from api.constants import AIClientConfig

# Configuração do logger
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Decorador para registrar automaticamente os clientes de IA
AI_CLIENT_MAPPING = {}

def register_ai_client(cls):
    """Decorador para registrar automaticamente classes de clientes de IA."""
    AI_CLIENT_MAPPING[cls.name] = cls
    return cls

class APIClient:
    """
    Classe base abstrata para implementação de clientes de IA.

    Attributes:
        name (str): Nome identificador do cliente.
        can_train (bool): Indica se o cliente suporta treinamento.
        supports_system_message (bool): Indica se a API suporta envio de mensagem do sistema.
        api_key (str): Chave de API para autenticação.
        model_name (str): Nome do modelo de IA a ser usado.
        configurations (dict): Configurações específicas do cliente.
    """
    name = ''
    can_train = False
    supports_system_message = True  # NOVO: indica suporte nativo a System Message

    def __init__(self, config: AIClientConfig):
        self.api_key = config.api_key
        self.model_name = config.model_name
        self.configurations = config.configurations.copy() if config.configurations else {}
        self.base_instruction = config.base_instruction or ""
        self.prompt = config.prompt or ""
        self.responses = config.responses or ""
        self.api_url = config.api_url or None
        self.use_system_message = config.use_system_message  # NOVO: define se o usuário deseja usar System Message
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
            # Lógica para combinar ou não system message
            if self.use_system_message and self.supports_system_message:
                return {
                    'base_instruction': base_instruction,
                    'user_prompt': prompt
                }
            else:
                combined_prompt = (base_instruction + "\n" + prompt).strip()
                return {
                    'base_instruction': '',
                    'user_prompt': combined_prompt
                }
        except Exception as e:
            logger.error(f"{self.__class__.__name__}._prepare_prompts: Nenhuma mensagem retornada.")
            raise APICommunicationError("Nenhuma mensagem retornada.")
    
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
        Executa a comparação baseada nos dados fornecidos.

        Args:
            data (dict): Dicionário com parâmetros para construção dos prompts.

        Returns:
            tuple: Retorna (resposta da IA, mensagem do sistema, mensagem do usuário).
        """
        function_name = 'compare'
        logger.debug(f"{self.__class__.__name__}.{function_name}: Iniciando comparação.")
        prompts = self._prepare_prompts(**data)
        response = self._call_api(prompts)
        system_message = prompts.get('base_instruction', '')
        user_message = prompts.get('user_prompt', '')
        logger.debug(f"{self.__class__.__name__}.{function_name}: Comparação concluída com sucesso.")
        return (response, system_message, user_message)

    def _call_api(self, prompts: dict) -> str:
        """
        Método abstrato para chamar a API específica. Deve ser implementado pelas subclasses.
        """
        raise NotImplementedError(f"{self.name}: Subclasses devem implementar o método _call_api.")

@register_ai_client
class OpenAiClient(APIClient):  # Renomeado de ChatGPTClient para OpenAiClient
    """Cliente para interação com a API do ChatGPT.

    Implementa a interface para comunicação com o modelo GPT da OpenAI,
    incluindo suporte para fine-tuning e geração de respostas.
    """
    name = "OpenAi"
    can_train = True

    def config(self, config: AIClientConfig):
        """
        Recebe as configurações específicas para o ChatGPT
        e inicializa os atributos necessários do cliente.
        """
        super().__init__(config)
    
    def __init__(self, config: AIClientConfig):
        """
        Construtor para ChatGPTClient.

        Args:
            config (AIClientConfig): Objeto de configuração com informações
            como api_key, model_name e api_url.
        """
        self.config(config)
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
        function_name = '_call_api'
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({
                    "role": "system",
                    "content": prompts['base_instruction']
                })
            messages.append({
                "role": "user", 
                "content": prompts['user_prompt']
            })

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages

            response = self.client.chat.completions.create(**self.configurations)

            logger.debug(f"{self.__class__.__name__}.{function_name}: Chat criado e concluído com sucesso.")

            if not response:
                logger.error(f"{self.__class__.__name__}.{function_name}: Nenhuma mensagem retornada.")
                raise APICommunicationError("Nenhuma mensagem retornada.")

            if isinstance(response, list) and response:
                response = response[0]

            if not hasattr(response, 'choices') or not isinstance(response.choices, list):
                error_message = getattr(response, 'model_extra', {}).get('error', 'Unknown error')
                raise APICommunicationError(f"{error_message}")

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

    def train(self, training_file, parameters={}):
        """
        Implementa o treinamento para o ChatGPT.
        """        
        function_name = 'train'
        logger.info(f"{self.__class__.__name__}.{function_name}: Treinamento iniciado.")
        temp_file_path = None  # Inicializa a variável para garantir que exista no finalmente
        try:
            # Ler o conteúdo JSON do arquivo de treinamento
            with training_file.open('r') as f:
                raw_training_data = json.load(f)
            
            # Certifique-se de que raw_training_data é uma lista de exemplos
            if not isinstance(raw_training_data, list):
                raise ValueError("O arquivo de treinamento deve conter uma lista de exemplos.")
            
            # Converter para JSONL no formato desejado
            jsonl_data = "\n".join([
                json.dumps({
                    "messages": [
                        {"role": "system", "content": training_example.get("system_message", "")},
                        {"role": "user", "content": training_example.get("user_message", "")},
                        {"role": "assistant", "content": training_example.get("response", "")}
                    ]
                }) 
                for training_example in raw_training_data
            ])
            
            # Salvar o conteúdo JSONL em um arquivo temporário
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl') as temp_file:
                temp_file.write(jsonl_data)
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
                    logger.debug(f"{self.__class__.__name__}.{function_name}: Modelo treinado.")
                    return status.fine_tuned_model
                elif status_state == 'failed':
                    raise APICommunicationError(f"{status.error}")
                else:
                    time.sleep(5)

        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao treinar o modelo: {e}")
            raise APICommunicationError("Erro ao treinar o modelo: {e}")

@register_ai_client
class GeminiClient(APIClient):
    """Cliente para interação com a API do Google Gemini.

    Implementa a interface para comunicação com o modelo Gemini do Google,
    incluindo suporte para treinamento e geração de conteúdo.
    """
    name = "Gemini"
    can_train = True
    
    def __init__(self, config: AIClientConfig):
        """
        Construtor para GeminiClient, inicializando e configurando o cliente
        generativeai com a api_key fornecida.

        Args:
            config (AIClientConfig): Objeto de configuração que contém a api_key
            e outras configurações necessárias.
        """
        super().__init__(config)
        genai.configure(api_key=self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API do Gemini.
        """
        function_name = '_call_api'
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({
                    "role": "system",
                    "content": prompts['base_instruction']
                })
            messages.append({
                "role": "user",
                "content": prompts['user_prompt']
            })
            combined_prompt = ""
            for m in messages:
                combined_prompt += f"{m['role'].upper()}: {m['content']}\n"
            gemini_config = genai.types.GenerationConfig(**self.configurations)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=None  # removido para usar combined_prompt
            )
            m = model.generate_content(combined_prompt, generation_config=gemini_config)
            return m.text
        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

    def train(self, training_file, parameters={}):
        """
        Executa o treinamento do modelo Gemini com base nos dados e parâmetros
        fornecidos.

        Args:
            training_file: Arquivo contendo dados em formato JSON.
            parameters (dict): Parâmetros de configuração para o treinamento.

        Returns:
            str: Nome do modelo treinado.
        """
        function_name = 'train'
        logger.info(f"{self.__class__.__name__}.{function_name}: Treinamento iniciado.")
        try:
            # Ler o conteúdo JSON do arquivo de treinamento
            with training_file.open('r') as f:
                raw_training_data = json.load(f)

            # Preparar os dados de treinamento no formato esperado
            training_data = []
            for training_example in raw_training_data:
                text_input = training_example.get('user_message', '')
                output = training_example.get('response', '')
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
            logger.debug(f"{self.__class__.__name__}.{function_name}: Operação de treinamento iniciada com sucesso.")

            # Aguardar a conclusão do treinamento
            while not operation.done():
                logger.debug(f"{self.__class__.__name__}.{function_name}: Treinamento em andamento...")
                time.sleep(10)  # Aguarda 10 segundos antes de verificar novamente

            result = operation.result()
            trained_model_name = result.name  # Nome do modelo treinado
            logger.debug(f"{self.__class__.__name__}.{function_name}: Treinamento concluído. Modelo treinado: {trained_model_name}")
            return trained_model_name
        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao treinar o modelo: {e}")
            raise APICommunicationError("Erro ao treinar o modelo: {e}")

@register_ai_client
class AnthropicClient(APIClient):  # Renomeado de Claude3Client para AnthropicClient
    """Cliente para interação com a API do Anthropic Claude 3.

    Implementa a interface para comunicação com o modelo Claude 3,
    focando na geração de respostas precisas.
    """
    name = "Anthropic"
    can_train = False
    
    def __init__(self, config: AIClientConfig):
        """
        Construtor para Claude3Client, que configura o cliente anthropic
        utilizando a api_key fornecida.

        Args:
            config (AIClientConfig): Configurações necessárias para inicializar
            o cliente Anthropic.
        """
        super().__init__(config)
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API do Claude 3.
        """
        function_name = '_call_api'
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
            if system.strip():
                self.configurations['system'] = system
            self.configurations['messages'] = messages
            self.configurations['max_tokens'] = self.configurations.get('max_tokens', 1024)

            response = self.client.messages.create(
                **self.configurations
            )

            logger.debug(f"{self.__class__.__name__}.{function_name}: Mensagem enviada e resposta recebida com sucesso.")

            if not response or not response.content or not response.content[0].text:
                logger.error(f"{self.__class__.__name__}.{function_name}: Nenhuma mensagem retornada.")
                raise APICommunicationError("Nenhuma mensagem retornada.")

            return response.content[0].text

        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

@register_ai_client
class PerplexityClient(APIClient):
    """Cliente para interação com a API da Perplexity.

    Implementa a interface para comunicação com os modelos da Perplexity,
    fornecendo capacidades de geração de texto.
    """
    name = "Perplexity"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o PerplexityClient, responsável por configurar
        previamente o cliente para comunicação com a API da Perplexity.

        Args:
            config (AIClientConfig): Objeto de configuração com api_key,
            model_name e outras informações.
        """
        super().__init__(config)

    def _call_api(self, prompts: dict) -> str:
        """
        Implementa a chamada à API da Perplexity.
        """
        function_name = '_call_api'
        try:
            url = self.api_url if self.api_url else "https://api.perplexity.ai/chat/completions"

            messages = []
            if prompts['base_instruction'].strip():
                messages.append({
                    "role": "system",
                    "content": prompts['base_instruction']
                })
            messages.append({
                "role": "user",
                "content": prompts['user_prompt']
            })

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.debug(f"{self.__class__.__name__}.{function_name}: Enviando solicitação para a API.")
            response = requests.post(url, json= self.configurations, headers=headers)

            # Verificar o status da resposta
            if response.status_code != 200:
                logger.error(f"{self.__class__.__name__}.{function_name}: API retornou o código de status {response.status_code}")
                raise APICommunicationError(f"API retornou o código de status {response.status_code}")

            response_json = response.json()

            # Extrair o texto gerado da resposta
            generated_text = response_json['choices'][0]['message'].get('content', '')

            if not generated_text:
                logger.error(f"{self.__class__.__name__}.{function_name}: Nenhum texto retornado na resposta.")
                raise APICommunicationError("Nenhum texto retornado na resposta.")

            logger.debug(f"{self.__class__.__name__}.{function_name}: Resposta recebida com sucesso.")

            return generated_text

        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

@register_ai_client
class LlamaClient(APIClient):
    """
    Cliente para interação com a API do Llama.

    Implementa a interface para comunicação com o modelo Llama,
    fornecendo capacidades de geração de texto.
    """
    name = "Llama"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o LlamaClient.

        Args:
            config (AIClientConfig): Objeto de configuração contendo a
            api_key e o model_name, entre outras informações.
        """
        super().__init__(config)
        self.client = LlamaAPI(self.api_key)

    def _call_api(self, prompts: dict) -> str:
        function_name = '_call_api'
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({
                    "role": "system",
                    "content": prompts['base_instruction']
                })
            messages.append({
                "role": "user",
                    "content": prompts['user_prompt']
            })

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages
            self.configurations['stream'] = self.configurations.get('stream', False)

            response = self.client.run(self.configurations)          

            if not response:
                logger.error(f"{function_name}: Nenhum texto retornado na resposta.")
                raise APICommunicationError("Nenhum texto retornado na resposta.")
            
            response = response.json()

            if "choices" not in response:

                s = response[0].get('error', 'Unknown error')

                # 1) Se possível, separe o código de status do "dicionário"
                parts = s.split(": ", 1)
                if len(parts) == 2:
                    _, dict_str = parts

                    # 2) Converta a parte do dicionário em um objeto Python
                    data = ast.literal_eval(dict_str)

                    # 3) Extraia o valor da chave "error"
                    error_message = data["error"]
                else:
                    error_message = s

                raise APICommunicationError(f"{error_message}")

            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"{e}")

@register_ai_client
class AzureOpenAIClient(OpenAiClient):  # Atualizado para herdar de OpenAiClient
    """
    Cliente para interação com a API do Azure OpenAI.

    Implementa a interface para comunicação com o modelo OpenAI
    hospedado no Azure, fornecendo capacidades de geração de texto.
    """
    name = "AzureOpenAI"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o AzureOpenAIClient, configurando o cliente AzureOpenAI
        com os parâmetros adequados.

        Args:
            config (AIClientConfig): Configura as informações necessárias
            para acessar o serviço Azure OpenAI.
        """
        super().config(config)

        self.client = AzureOpenAI(  
            azure_endpoint=self.api_url,  
            api_key=self.api_key,
            api_version="2024-05-01-preview"
        )

@register_ai_client
class AzureClient(APIClient):
    """
    Cliente para interação com a API do Azure.

    Implementa a interface para comunicação com o modelo de IA
    hospedado no Azure, fornecendo capacidades de geração de texto.
    """
    name = "Azure"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o AzureClient, responsável por inicializar o cliente
        ChatCompletionsClient usando as credenciais do Azure.

        Args:
            config (AIClientConfig): Contém a api_key e informações de endpoint
            para se conectar ao serviço Azure.
        """
        super().__init__(config)

        # Configuração do transporte com timeout aumentado
        #transport = RequestsTransport(connection_timeout=1200, read_timeout=1200)  # 1200 segundos de timeout


        self.client = ChatCompletionsClient(
            endpoint=self.api_url,
            credential=AzureKeyCredential(self.api_key),
            #transport=transport
        )

    def _call_api(self, prompts: dict) -> str:
        function_name = '_call_api'
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({
                    "role": "system",
                    "content": prompts['base_instruction']
                })
            messages.append({
                "role": "user", 
                "content": prompts['user_prompt']
            })

            self.configurations['messages'] = messages

            response = self.client.complete(**self.configurations)

            logger.debug(f"{self.__class__.__name__}.{function_name}: Chat criado e concluído com sucesso.")

            if not response:
                logger.error(f"{self.__class__.__name__}.{function_name}: Nenhuma mensagem retornada.")
                raise APICommunicationError("Nenhuma mensagem retornada.")

            if not isinstance(response.choices, list):
                error_message = response[0].model_extra.get('error', 'Unknown error')
                raise APICommunicationError(f"{error_message}")
            
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"{self.__class__.__name__}.{function_name}: Erro ao comunicar com a API: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")


