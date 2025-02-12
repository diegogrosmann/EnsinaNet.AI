"""
Este módulo fornece utilitários e clientes para interagir com diferentes APIs de IA.

Classes:
    APIClient: Classe base para todos os clientes de IA
    OpenAiClient: Cliente para OpenAI GPT
    GeminiClient: Cliente para Google Gemini
    AnthropicClient: Cliente para Anthropic Claude
    PerplexityClient: Cliente para Perplexity
    LlamaClient: Cliente para Llama
    AzureOpenAIClient: Cliente para Azure OpenAI
    AzureClient: Cliente para Azure

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

# (NOVO) Import do circuito
from api.utils.circuit_breaker import (
    attempt_call,
    record_failure,
    record_success,
    CircuitOpenError
)

# Configuração do logger
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Decorador para registrar automaticamente classes de clientes de IA
AI_CLIENT_MAPPING = {}

def register_ai_client(cls):
    """Decorador para registrar automaticamente classes de clientes de IA.

    Args:
        cls (class): Classe do cliente de IA.

    Returns:
        class: A mesma classe registrada.
    """
    AI_CLIENT_MAPPING[cls.name] = cls
    return cls

class APIClient:
    """Classe base abstrata para implementação de clientes de IA.

    Attributes:
        name (str): Nome identificador do cliente.
        can_train (bool): Indica se o cliente suporta treinamento.
        supports_system_message (bool): Indica se a API suporta envio de System Message.
        api_key (str): Chave de API para autenticação.
        model_name (str): Nome do modelo de IA a ser usado.
        configurations (dict): Configurações específicas do cliente.
        base_instruction (str): Instrução base (opcional).
        prompt (str): Prompt personalizado (opcional).
        responses (str): Respostas personalizadas (opcional).
        api_url (str): URL da API (opcional).
        use_system_message (bool): Se deve usar "system message" (caso suportado).
    """
    name = ''
    can_train = False
    supports_system_message = True  # NOVO: indica suporte nativo a System Message

    def __init__(self, config: AIClientConfig):
        """
        Construtor para a classe base de clientes de IA.

        Args:
            config (AIClientConfig): Configurações de IA (api_key, model_name etc.).
        """
        self.api_key = config.api_key
        self.model_name = config.model_name
        self.configurations = config.configurations.copy() if config.configurations else {}
        self.base_instruction = config.base_instruction or ""
        self.prompt = config.prompt or ""
        self.responses = config.responses or ""
        self.api_url = config.api_url or None
        self.use_system_message = config.use_system_message

        if not self.api_key:
            raise MissingAPIKeyError(f"{self.name}: Chave de API não configurada.")
        logger.debug(f"{self.__class__.__name__}.__init__: Inicializado com configurações: {self.configurations}")

    def _render_template(self, template: str, context: dict):
        """Renderiza um template usando a engine do Django.

        Args:
            template (str): Template em formato de string.
            context (dict): Dicionário de contexto.

        Returns:
            str: Template renderizado.
        """
        django_engine = engines['django']
        template_engine = django_engine.from_string(template)
        return template_engine.render(context)

    def _prepare_prompts(self, **kwargs) -> dict:
        """Prepara os prompts para a API de IA.

        Args:
            **kwargs: Parâmetros para a preparação do prompt.

        Returns:
            dict: Dicionário com 'base_instruction' e 'user_prompt'.

        Raises:
            APICommunicationError: Se houver erro na preparação.
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
            logger.error(f"{self.__class__.__name__}._prepare_prompts: Nenhuma mensagem retornada. Detalhe: {e}")
            raise APICommunicationError("Nenhuma mensagem retornada.")

    def _prepare_train(self, **kwargs) -> str:
        """
        Prepara dados de treinamento para fine-tuning, caso exista um arquivo de treinamento.

        Args:
            **kwargs: Pode conter 'training_file'.

        Returns:
            str: String com exemplos, pronta para ser anexada ao prompt.
        """
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
                    training_examples += f"Exemplo:\n Mensagem do Sistema: {system_message}\n"\
                                         f"Mensagem do Usuário: {user_message}\n"\
                                         f"Resposta esperada: {response}\n\n"
                training = training_examples
            except Exception as e:
                logger.error(f"{self.__class__.__name__}._prepare_train: Erro ao ler o arquivo de treinamento: {e}")
        return training

    def compare(self, data: dict) -> tuple:
        """
        Compara dados usando a API de IA.

        Args:
            data (dict): Dados para comparação.

        Returns:
            tuple: (resposta da IA, system_message, user_message).
        """
        prompts = self._prepare_prompts(**data)
        response = self._call_api(prompts)
        system_message = prompts.get('base_instruction', '')
        user_message = prompts.get('user_prompt', '')
        return (response, system_message, user_message)

    def _call_api(self, prompts: dict) -> str:
        """
        Método abstrato para chamar a API. 
        As subclasses devem implementar.

        Args:
            prompts (dict): Com 'base_instruction' e 'user_prompt'.

        Returns:
            str: Resposta da IA.

        Raises:
            NotImplementedError: Se não for sobrescrito pela subclasse.
        """
        raise NotImplementedError(f"{self.name}: Subclasses devem implementar o método _call_api.")

    def train(self, training_file, parameters={}):
        """
        Realiza o treinamento do modelo (fine-tuning) se suportado.

        Args:
            training_file: Arquivo de treinamento.
            parameters (dict): Parâmetros de treinamento (opcional).

        Returns:
            str: Nome do modelo treinado.

        Raises:
            NotImplementedError: Se a IA não suportar treinamento.
        """
        raise NotImplementedError("Este cliente não suporta treinamento.")


@register_ai_client
class OpenAiClient(APIClient):
    """Cliente para interação com a API da OpenAI."""

    name = "OpenAi"
    can_train = True

    def __init__(self, config: AIClientConfig):
        """
        Construtor para OpenAiClient.

        Args:
            config (AIClientConfig): Configurações necessárias (api_key, api_url, etc.).
        """
        super().__init__(config)
        args = {'api_key': self.api_key}
        if self.api_url is not None:
            args['base_url'] = self.api_url
        self.client = OpenAI(**args)

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada à API do OpenAI.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Conteúdo de resposta.

        Raises:
            APICommunicationError: Em caso de falha na comunicação.
        """
        # (NOVO) Tenta "fechar" o circuito se estiver aberto
        attempt_call(self.name)

        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({"role": "system", "content": prompts['base_instruction']})
            messages.append({"role": "user", "content": prompts['user_prompt']})

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages

            response = self.client.chat.completions.create(**self.configurations)

            if not response:
                raise APICommunicationError("Nenhuma mensagem retornada do OpenAI.")

            if hasattr(response, 'choices') and response.choices:
                # (NOVO) Deu certo => registra success no circuit
                record_success(self.name)
                return response.choices[0].message.content
            else:
                raise APICommunicationError("Resposta do OpenAI inválida.")

        except Exception as e:
            # (NOVO) Qualquer falha => registra failure
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                # Se for especificamente o circuito aberto, relançamos
                raise e
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com OpenAI: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

    def train(self, training_file, parameters={}):
        """
        Realiza fine-tuning do modelo OpenAI.

        Args:
            training_file: Arquivo de treinamento em JSON.
            parameters (dict): Parâmetros de fine-tuning.

        Returns:
            str: Nome do modelo treinado.

        Raises:
            APICommunicationError: Em caso de erro no processo de fine-tuning.
        """
        function_name = 'train'
        logger.info(f"{self.__class__.__name__}.{function_name}: Treinamento iniciado.")
        temp_file_path = None
        try:
            with training_file.open('r') as f:
                raw_training_data = json.load(f)

            if not isinstance(raw_training_data, list):
                raise ValueError("O arquivo de treinamento deve conter uma lista de exemplos.")

            jsonl_data = "\n".join([
                json.dumps({
                    "messages": [
                        {"role": "system", "content": ex.get("system_message", "")},
                        {"role": "user", "content": ex.get("user_message", "")},
                        {"role": "assistant", "content": ex.get("response", "")}
                    ]
                })
                for ex in raw_training_data
            ])

            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl') as temp_file:
                temp_file.write(jsonl_data)
                temp_file_path = temp_file.name

            with open(temp_file_path, 'rb') as f:
                ai_file = self.client.files.create(file=f, purpose='fine-tune')

            job = self.client.fine_tuning.jobs.create(
                training_file=ai_file.id,
                model=self.model_name,
                hyperparameters=parameters
            )

            while True:
                status = self.client.fine_tuning.jobs.retrieve(job.id)
                if status.status == 'succeeded':
                    logger.debug(f"{self.__class__.__name__}.{function_name}: Modelo treinado com sucesso.")
                    return status.fine_tuned_model
                elif status.status == 'failed':
                    raise APICommunicationError(f"{status.error}")
                time.sleep(5)

        except Exception as e:
            logger.error(f"Erro ao treinar OpenAi: {e}")
            raise APICommunicationError(f"Erro ao treinar o modelo: {e}")


@register_ai_client
class GeminiClient(APIClient):
    """Cliente para interação com a API do Google Gemini."""

    name = "Gemini"
    can_train = True

    def __init__(self, config: AIClientConfig):
        """
        Construtor para GeminiClient, 
        inicializando e configurando generativeai com a api_key.

        Args:
            config (AIClientConfig): Contém api_key, model_name etc.
        """
        super().__init__(config)
        genai.configure(api_key=self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada à API do Gemini.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Texto gerado pela API.

        Raises:
            APICommunicationError: Em caso de falha na comunicação com Gemini.
        """
        attempt_call(self.name)
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({"role": "system", "content": prompts['base_instruction']})
            messages.append({"role": "user", "content": prompts['user_prompt']})

            combined_prompt = ""
            for m in messages:
                combined_prompt += f"{m['role'].upper()}: {m['content']}\n"

            gemini_config = genai.types.GenerationConfig(**self.configurations)
            model = genai.GenerativeModel(model_name=self.model_name, system_instruction=None)
            m = model.generate_content(combined_prompt, generation_config=gemini_config)

            record_success(self.name)
            return m.text
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient _call_api: Erro ao comunicar com Gemini: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

    def train(self, training_file, parameters={}):
        """
        Executa o treinamento do modelo Gemini.

        Args:
            training_file: Arquivo com dados de treinamento em formato JSON.
            parameters (dict): Parâmetros adicionais (epoch_count, batch_size etc.).

        Returns:
            str: Nome do modelo treinado.

        Raises:
            APICommunicationError: Em caso de erro no treinamento.
        """
        try:
            with training_file.open('r') as f:
                raw_training_data = json.load(f)

            training_data = []
            for example in raw_training_data:
                text_input = example.get('user_message', '')
                output = example.get('response', '')
                training_data.append({'text_input': text_input, 'output': output})

            display_name = parameters.get('display_name', 'Fine-tuned Model')
            epoch_count = int(parameters.get('epoch_count', 1))
            batch_size = int(parameters.get('batch_size', 4))
            learning_rate = float(parameters.get('learning_rate', 0.001))
            source_model = "models/" + self.model_name

            operation = genai.create_tuned_model(
                display_name=display_name,
                source_model=source_model,
                epoch_count=epoch_count,
                batch_size=batch_size,
                learning_rate=learning_rate,
                training_data=training_data,
            )

            while not operation.done():
                time.sleep(10)

            result = operation.result()
            return result.name
        except Exception as e:
            logger.error(f"Erro ao treinar Gemini: {e}")
            raise APICommunicationError(f"Erro ao treinar o modelo: {e}")


@register_ai_client
class AnthropicClient(APIClient):
    """Cliente para interação com a API do Anthropic (Claude 3)."""

    name = "Anthropic"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para AnthropicClient, configurando anthropic.Anthropic.

        Args:
            config (AIClientConfig): Contém api_key, model_name etc.
        """
        super().__init__(config)
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada à API do Claude 3.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Texto de resposta do Claude.

        Raises:
            APICommunicationError: Em caso de falha de rede ou resposta inválida.
        """
        attempt_call(self.name)
        try:
            system = prompts['base_instruction']
            user_prompt = prompts['user_prompt']

            self.configurations['model'] = self.model_name
            if system.strip():
                self.configurations['system'] = system
            self.configurations['messages'] = [{"role": "user", "content": user_prompt}]
            self.configurations['max_tokens'] = self.configurations.get('max_tokens', 1024)

            response = self.client.messages.create(**self.configurations)

            if not response or not response.content or not response.content[0].text:
                raise APICommunicationError("Nenhuma mensagem retornada de Anthropic.")

            record_success(self.name)
            return response.content[0].text

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"AnthropicClient _call_api: {e}")
            raise APICommunicationError(f"Erro ao comunicar com Anthropic: {e}")


@register_ai_client
class PerplexityClient(APIClient):
    """Cliente para interação com a API da Perplexity."""

    name = "Perplexity"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o PerplexityClient.

        Args:
            config (AIClientConfig): Contém api_key, model_name etc.
        """
        super().__init__(config)

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada à API da Perplexity.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Texto gerado pela Perplexity.

        Raises:
            APICommunicationError: Se a API retornar erro ou nenhum texto.
        """
        attempt_call(self.name)
        try:
            url = self.api_url if self.api_url else "https://api.perplexity.ai/chat/completions"

            messages = []
            if prompts['base_instruction'].strip():
                messages.append({"role": "system", "content": prompts['base_instruction']})
            messages.append({"role": "user", "content": prompts['user_prompt']})

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=self.configurations, headers=headers)

            if response.status_code != 200:
                raise APICommunicationError(f"API Perplexity retornou código {response.status_code}.")

            resp_json = response.json()
            generated_text = resp_json['choices'][0]['message'].get('content', '')

            if not generated_text:
                raise APICommunicationError("Nenhum texto retornado pela Perplexity.")

            record_success(self.name)
            return generated_text
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"PerplexityClient _call_api: {e}")
            raise APICommunicationError(f"Erro Perplexity: {e}")


@register_ai_client
class LlamaClient(APIClient):
    """Cliente para interação com a API do Llama."""

    name = "Llama"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o LlamaClient.

        Args:
            config (AIClientConfig): Contém api_key, model_name etc.
        """
        super().__init__(config)
        self.client = LlamaAPI(self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada à API do Llama.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Conteúdo retornado pela API do Llama.

        Raises:
            APICommunicationError: Se ocorrer erro na comunicação.
        """
        attempt_call(self.name)
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({"role": "system", "content": prompts['base_instruction']})
            messages.append({"role": "user", "content": prompts['user_prompt']})

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages
            self.configurations['stream'] = self.configurations.get('stream', False)

            response = self.client.run(self.configurations)

            if not response:
                raise APICommunicationError("Nenhum texto retornado de Llama.")

            response = response.json()
            if "choices" not in response:
                error_str = response[0].get('error', 'Erro Llama')
                raise APICommunicationError(error_str)

            record_success(self.name)
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"LlamaClient _call_api: {e}")
            raise APICommunicationError(f"Erro Llama: {e}")


@register_ai_client
class AzureOpenAIClient(OpenAiClient):
    """
    Cliente para interação com a API do Azure OpenAI.
    Herda a maior parte da lógica do OpenAiClient.
    """

    name = "AzureOpenAI"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para AzureOpenAIClient.

        Args:
            config (AIClientConfig): Configurações com azure_endpoint, api_key etc.
        """
        super().__init__(config)
        self.client = AzureOpenAI(
            azure_endpoint=self.api_url,
            api_key=self.api_key,
            api_version="2024-05-01-preview"
        )


@register_ai_client
class AzureClient(APIClient):
    """Cliente para interação com a API do Azure (ChatCompletionsClient)."""

    name = "Azure"
    can_train = False

    def __init__(self, config: AIClientConfig):
        """
        Construtor para o AzureClient.

        Args:
            config (AIClientConfig): Contém api_key e api_url.
        """
        super().__init__(config)
        self.client = ChatCompletionsClient(
            endpoint=self.api_url,
            credential=AzureKeyCredential(self.api_key),
        )

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada à API do Azure.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Conteúdo retornado.

        Raises:
            APICommunicationError: Se não houver resposta válida.
        """
        attempt_call(self.name)
        try:
            messages = []
            if prompts['base_instruction'].strip():
                messages.append({"role": "system", "content": prompts['base_instruction']})
            messages.append({"role": "user", "content": prompts['user_prompt']})
            self.configurations['messages'] = messages

            response = self.client.complete(**self.configurations)

            if not response:
                raise APICommunicationError("Nenhuma mensagem retornada de Azure.")

            if not hasattr(response, 'choices') or not response.choices:
                raise APICommunicationError("Resposta inválida da Azure API")

            record_success(self.name)
            return response.choices[0].message.content

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"AzureClient _call_api: {e}")
            raise APICommunicationError(f"Erro Azure: {e}")
