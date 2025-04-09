"""Clientes para diferentes APIs de IA."""
from datetime import datetime, time
from typing import Any, Dict, TypeVar, Tuple

import uuid
import anthropic
from google import genai
from google.genai import types as google_types
import requests

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from llamaapi import LlamaAPI
from openai import AzureOpenAI, OpenAI
import html
import json
import logging
import os
import tempfile
from dotenv import load_dotenv
from openai.types import FileObject
from openai.types.fine_tuning import FineTuningJob

from core.types import (
    AIComparisonData,
    AIComparisonResponse,
    AIConfig,
    AIMessage,
    AISingleComparisonData,
    AISuccess,
    AITrainingFileData,
    AITrainingStatus,
    AITrainingResponse,
    APIFileCollection,
    APIModel,
    APIModelCollection,
    JSONDict,
)
from core.exceptions import APICommunicationError, MissingAPIKeyError
from django.template import engines
from api.utils.circuit_breaker import (
    attempt_call,
    record_failure,
    record_success,
)

# Configuração
logger = logging.getLogger(__name__)
load_dotenv()

# Tipos
T = TypeVar('T')
AI_CLIENT_MAPPING: Dict[str, type] = {}

def register_ai_client(cls: type) -> type:
    """Registra uma classe de cliente de IA no mapeamento global.
    
    Args:
        cls: Classe do cliente a ser registrada.
    
    Returns:
        A mesma classe, permitindo uso como decorador.
    """
    AI_CLIENT_MAPPING[cls.name] = cls
    logger.debug(f"Cliente de IA registrado: {cls.name}")
    return cls

class APIClient:
    """Classe base abstrata para implementação de clientes de IA.
    
    Define a interface comum e funcionalidades básicas que todos os
    clientes de IA devem implementar.
    
    Attributes:
        name: Nome identificador do cliente.
        can_train: Se suporta treinamento.
        supports_system_message: Se aceita mensagem do sistema.
        api_key: Chave de API para autenticação.
        api_url: URL base da API (opcional).
        model_name: Nome/ID do modelo a ser usado.
        configurations: Configurações específicas do cliente.
        base_instruction: Instrução base para prompts.
        prompt: Template de prompt personalizado.
        responses: Template de respostas.
        use_system_message: Se deve usar mensagem do sistema.
        training_configurations: Configurações específicas para treinamento.
    """
    
    name = ''
    can_train = False
    supports_system_message = True

    def __init__(self, config: AIConfig) -> None:
        
        # Configura atributos básicos
        self.api_key = config.api_key
        self.api_url = config.api_url
        self.model_name = config.model_name or ''
        self.configurations = config.configurations or {}
        self.use_system_message = config.use_system_message
        self.training_configurations = config.training_configurations or {}

        # Configura dados de prompt se disponíveis
        if config.prompt_config:
            self.base_instruction = config.prompt_config.base_instruction
            self.prompt = config.prompt_config.prompt
            self.responses = config.prompt_config.response
        else:
            self.base_instruction = ''
            self.prompt = ''
            self.responses = ''

        if not self.api_key:
            raise MissingAPIKeyError(f"{self.name}: Chave de API não configurada.")
        
        logger.debug(f"[{self.name}] {self.__class__.__name__}.__init__: Inicializado com configurações: {self.configurations}")

    def _render_template(self, template: str, context: JSONDict) -> str:
        """Renderiza um template usando a engine Django.
        
        Args:
            template: Template em formato string.
            context: Variáveis para renderização.
            
        Returns:
            Template renderizado.
            
        Raises:
            APICommunicationError: Se falhar ao renderizar.
        """
        try:
            django_engine = engines['django']
            template_engine = django_engine.from_string(template)
            return template_engine.render(context)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao renderizar template: {e}")
            raise APICommunicationError(f"Erro ao processar template: {e}")

    def _prepare_prompts(self, data: AISingleComparisonData) -> AIMessage:
        """Prepara os prompts para envio à API.
        
        Args:
            data: Objeto com dados para comparação.
            
        Returns:
            AIMessage com 'system_message' e 'user_message'.
        """
        try:
            data_dict = data.__dict__ if hasattr(data, '__dict__') else data._asdict()
            data_dict['ai_name'] = self.name
            data_dict['answer_format'] = self.responses

            base_instruction = html.unescape(self._render_template(self.base_instruction, data_dict))
            prompt = html.unescape(self._render_template(self.prompt, data_dict))

            if self.use_system_message and self.supports_system_message:
                return AIMessage(
                    system_message=base_instruction,
                    user_message=prompt
                )
            else:
                combined_prompt = (base_instruction + "\n" + prompt).strip()
                return AIMessage(
                    system_message='',
                    user_message=combined_prompt
                )
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao preparar prompts: {e}")
            raise APICommunicationError(f"Erro ao preparar prompts: {e}")

    def compare(self, data: AISingleComparisonData) -> Tuple[AIComparisonResponse, AIMessage]:
        """Compara dados usando a API de IA.
        
        Args:
            data: Dados para comparação.
            
        Returns:
            Tupla (resposta_ia, system_message, user_message).
        """
        try:
            logger.debug(f"[{self.name}] Iniciando comparação de dados")
            message = self._prepare_prompts(data)
            response = self._call_api(message)
            return (response, message)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao comparar dados: {e}")
            raise APICommunicationError(f"Erro na comparação: {e}")

    def _call_api(self, prompts: AIMessage) -> AIComparisonResponse:
        """Método abstrato para chamar a API específica.
        
        Args:
            prompts: Dicionário com prompts preparados.
            
        Returns:
            AIComparisonResponse: Resposta da API com metadados.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _call_api")

    def _prepare_train(self, file: AITrainingFileData) -> Any:
        """
        Prepara os dados para treinamento.
        
        Args:
            file: Objeto com dados do arquivo de treinamento.
            
        Returns:
            Dados preparados no formato específico de cada IA.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _prepare_train")

    def train(self, file: AITrainingFileData) -> AITrainingResponse:
        """
        Prepara e inicia o treinamento.
        
        Args:
            file_path: Caminho do arquivo de treinamento.
            
        Returns:
            AITrainingResponse: Resultado inicial do treinamento com job_id.
            
        Raises:
            NotImplementedError: Se a IA não suportar treinamento.
        """
        if not self.can_train:
            logger.warning(f"[{self.name}] Tentativa de treinamento em cliente sem suporte a treinamento")
            raise NotImplementedError(f"[{self.name}] Este cliente não suporta treinamento.")

        prepared_file_data = self._prepare_train(file)
        try:
            return self._start_training(prepared_file_data)
        finally:
            # Verifique se prepared_file_data é um caminho de string antes de tentar excluir
            if (isinstance(prepared_file_data, str) and 
            prepared_file_data != file.file_path and 
            os.path.exists(prepared_file_data)):
                try:
                    os.remove(prepared_file_data)
                except Exception as e:
                    logger.warning(f"[{self.name}] Erro ao remover arquivo temporário {prepared_file_data}: {e}")

    def _start_training(self, training_data: Any) -> AITrainingResponse:
        """Método abstrato para iniciar treinamento.
        
        Args:
            training_data: Dados preparados para treinamento.
            
        Returns:
            AITrainingResponse: Resultado inicial do treinamento.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _start_training")

    def get_training_status(self, job_id: str) -> AITrainingResponse:
        """
        Verifica o status atual do treinamento.
        
        Args:
            job_id: ID do job de treinamento.
            
        Returns:
            AITrainingResponse: Status atual do treinamento.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar get_training_status.")

    def _call_train_api(self, training_data: str) -> APIModel:
        """
        Método abstrato para chamar a API de treinamento.
        As subclasses que suportam treinamento devem implementar.
        
        Args:
            training_data (str): Dados de treinamento preparados.
            
        Returns:
            str: Nome do modelo treinado.
            
        Raises:
            NotImplementedError: Se não for sobrescrito pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar o método _call_train_api.")

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True) -> APIModelCollection:
        """
        Lista os modelos treinados disponíveis.
        
        Returns:
            list: Lista de modelos treinados.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar list_trained_models.")

    def cancel_training(self, id: str) -> AISuccess:
        """
        Cancela um job de treinamento em andamento.
        
        Args:
            id: ID do job a ser cancelado.
            
        Returns:
            bool: True se cancelado com sucesso.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar cancel_training.")

    def delete_trained_model(self, model_name: str) -> AISuccess:
        """
        Remove um modelo treinado.
        
        Args:
            model_name (str): Nome/ID do modelo a ser removido.
            
        Returns:
            bool: True se removido com sucesso.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar delete_trained_model.")

    def api_list_files(self) -> APIFileCollection:
        """
        Lista todos os arquivos.
        
        Returns:
            list: Lista de arquivos.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar list_training_files.")

    def delete_file(self, file_id: str) -> AISuccess:
        """
        Remove um arquivo.
        
        Args:
            file_id (str): ID do arquivo a ser removido.
            
        Returns:
            bool: True se removido com sucesso.
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar delete_training_file.")

@register_ai_client
class OpenAiClient(APIClient):
    """Cliente para interação com a API da OpenAI."""
    name = "OpenAi"
    can_train = True

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        args = {'api_key': self.api_key}
        if self.api_url is not None:
            args['base_url'] = self.api_url
        self.client = OpenAI(**args)

    def _call_api(self, message: AIMessage) -> AIComparisonResponse:
        logger.debug(f"[{self.name}] Iniciando chamada para OpenAI")
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            messages = []
            if message.system_message.strip():
                messages.append({"role": "system", "content": message.system_message})
            messages.append({"role": "user", "content": message.user_message})
            
            request_config = {
                "model": self.model_name,
                "messages": messages,
                **self.configurations
            }
            
            response = self.client.chat.completions.create(**request_config)
            if not response:
                logger.error(f"{self.__class__.__name__}._call_api: Nenhuma mensagem retornada do OpenAI.")
                raise APICommunicationError("Nenhuma mensagem retornada do OpenAI.")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if hasattr(response, 'choices') and response.choices:
                record_success(self.name)
                logger.debug(f"[{self.name}] Chamada concluída com sucesso")
                return AIComparisonResponse(
                    response=response.choices[0].message.content,
                    model_name=self.model_name,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
            else:
                logger.error(f"{self.__class__.__name__}._call_api: Resposta do OpenAI inválida: {response}")
                raise APICommunicationError("Resposta do OpenAI inválida.")
        except APICommunicationError as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=str(e)
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com OpenAI: {e}")
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=f"Erro ao comunicar com a API: {e}"
            )

    def _prepare_train(self, file: AITrainingFileData) -> str:
        try:
            with open(file.file_path, 'r') as f:
                training_data = json.load(f)
            temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl')
            for example in training_data:
                messages = []
                if example.get('system_message'):
                    messages.append({
                        "role": "system",
                        "content": example['system_message']
                    })
                messages.append({
                    "role": "user",
                    "content": example['user_message']
                })
                messages.append({
                    "role": "assistant",
                    "content": example['response']
                })
                conversation = {"messages": messages}
                temp_file.write(json.dumps(conversation) + '\n')
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.error(f"Erro ao preparar arquivo de treinamento: {e}")
            raise APICommunicationError(f"Erro ao preparar arquivo: {e}")

    def _start_training(self, training_data: Any) -> AITrainingResponse:
        attempt_call(self.name)
        try:
            file_obj: FileObject
            with open(training_data, 'rb') as f:
                file_obj = self.client.files.create(file=f, purpose='fine-tune')
            training_type = "supervised"
            training_params = {}
            if self.training_configurations:
                if 'type' in self.training_configurations:
                    training_type = self.training_configurations.pop('type')
                training_params = self.training_configurations
            job: FineTuningJob = self.client.fine_tuning.jobs.create(
                training_file=file_obj.id,
                model=self.model_name,
                hyperparameters=training_params
            )
            record_success(self.name)
            return AITrainingResponse(
                job_id=job.id,
                status=AITrainingStatus.IN_PROGRESS,
                model_name=None,
                error=None,
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )
        except Exception as e:
            record_failure(self.name)
            logger.error(f"OpenAiClient _start_training: {e}")
            return AITrainingResponse(
                job_id="",
                status=AITrainingStatus.FAILED,
                model_name=None,
                error=str(e),
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )
        finally:
            try:
                if os.path.exists(training_data):
                    os.unlink(training_data)
            except Exception as e:
                logger.warning(f"Não foi possível remover arquivo temporário {training_data}: {e}")

    def get_training_status(self, job_id: str) -> AITrainingResponse:
        attempt_call(self.name)
        try:
            status_obj = self.client.fine_tuning.jobs.retrieve(job_id)
            if status_obj.status == 'succeeded':
                return AITrainingResponse(
                    job_id=job_id,
                    status=AITrainingStatus.COMPLETED,
                    model_name=status_obj.fine_tuned_model,
                    error=None,
                    completed_at=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    progress=1.0
                )
            elif status_obj.status == 'failed':
                progress = 0.0
                if (hasattr(status_obj, 'trained_tokens') and hasattr(status_obj, 'training_file_tokens') 
                        and status_obj.training_file_tokens):
                    progress = status_obj.trained_tokens / status_obj.training_file_tokens
                return AITrainingResponse(
                    job_id=job_id,
                    status=AITrainingStatus.FAILED,
                    model_name=None,
                    error=getattr(status_obj, 'error', 'Falha desconhecida'),
                    completed_at=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    progress=progress
                )
            else:
                progress = 0.0
                if (hasattr(status_obj, 'trained_tokens') and hasattr(status_obj, 'training_file_tokens') 
                        and status_obj.training_file_tokens):
                    progress = status_obj.trained_tokens / status_obj.training_file_tokens
                return AITrainingResponse(
                    job_id=job_id,
                    status=AITrainingStatus.IN_PROGRESS,
                    model_name=None,
                    error=None,
                    completed_at=None,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    progress=progress
                )
        except APICommunicationError:
            record_failure(self.name)
            raise
        except Exception as e:
            record_failure(self.name)
            logger.error(f"OpenAiClient get_training_status: {e}")
            raise APICommunicationError(f"Erro ao verificar status: {e}")

@register_ai_client
class GeminiClient(APIClient):
    """Cliente para interação com a API do Google Gemini."""
    name = "Gemini"
    can_train = True

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        self.client = genai.Client(api_key=self.api_key)

    def _call_api(self, message: AIMessage) -> AIComparisonResponse:
        attempt_call(self.name)
        logger.debug(f"[{self.name}] Iniciando chamada para Gemini")
        start_time = datetime.now()
        try:
            request_config = self.configurations.copy()
            config_obj = None
            
            if message.system_message.strip():
                system_instruction = [google_types.Part.from_text(text=message.system_message)]
                config_obj = google_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    **request_config
                )
            else:
                config_obj = google_types.GenerateContentConfig(**request_config)
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=message.user_message,
                config=config_obj
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            record_success(self.name)
            logger.debug(f"[{self.name}] Chamada concluída com sucesso")
            
            return AIComparisonResponse(
                response=response.text,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationError as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=str(e)
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"GeminiClient _call_api: Erro ao comunicar com Gemini: {e}")
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=f"Erro ao comunicar com a API: {e}"
            )

    def _prepare_train(self, file: AITrainingFileData) -> google_types.TuningDataset:
        try:
            with open(file.file_path, 'r') as f:
                training_data = json.load(f)
            examples = []
            for item in training_data:
                text_input = item['user_message']
                if item.get('system_message'):
                    text_input = f"{item['system_message']}\n {text_input}"
                examples.append(
                    google_types.TuningExample(
                        text_input=text_input,
                        output=item['response']
                    )
                )
            return google_types.TuningDataset(examples=examples)
        except Exception as e:
            logger.error(f"GeminiClient _prepare_train: Erro ao preparar dados: {e}")
            raise APICommunicationError(f"Erro ao preparar dados de treinamento: {e}")

    def _start_training(self, training_data: Any) -> AITrainingResponse:
        attempt_call(self.name)
        try:
            if 'tuned_model_display_name' not in self.training_configurations:
                random_suffix = uuid.uuid4().hex[:8]
                display_name = f"{self.model_name}-Tuned-{random_suffix}"
                display_name = display_name[:40]
                self.training_configurations['tuned_model_display_name'] = display_name
            config_obj = google_types.CreateTuningJobConfig(**self.training_configurations)
            tuning_job = self.client.tunings.tune(
                base_model=self.model_name if '/' in self.model_name else f'models/{self.model_name}',
                training_dataset=training_data,
                config=config_obj
            )
            record_success(self.name)
            return AITrainingResponse(
                job_id=tuning_job.name,
                status=AITrainingStatus.IN_PROGRESS,
                model_name=None,
                error=None,
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )
        except Exception as e:
            record_failure(self.name)
            logger.error(f"GeminiClient _start_training: {e}")
            return AITrainingResponse(
                job_id="",
                status=AITrainingStatus.FAILED,
                model_name=None,
                error=str(e),
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )

    def get_training_status(self, job_id: str) -> AITrainingResponse:
        attempt_call(self.name)
        try:
            operation = self.client.tunings.get(name=job_id)
            if operation.has_ended:
                if operation.has_succeeded:
                    return AITrainingResponse(
                        job_id=job_id,
                        status=AITrainingStatus.COMPLETED,
                        model_name=operation.name,
                        error=None,
                        completed_at=operation.end_time,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        progress=1.0
                    )
                else:
                    return AITrainingResponse(
                        job_id=job_id,
                        status=AITrainingStatus.FAILED,
                        model_name=None,
                        error=str(operation.error),
                        completed_at=datetime.now(),
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        progress=1.0
                    )
            else:
                progress = 0.0
                if hasattr(operation, 'trained_tokens') and hasattr(operation, 'training_file_tokens') and operation.training_file_tokens:
                    progress = operation.trained_tokens / operation.training_file_tokens
                return AITrainingResponse(
                    job_id=job_id,
                    status=AITrainingStatus.IN_PROGRESS,
                    model_name=None,
                    error=None,
                    completed_at=None,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    progress=progress
                )
        except APICommunicationError:
            record_failure(self.name)
            raise
        except Exception as e:
            return AITrainingResponse(
                job_id=job_id,
                status=AITrainingStatus.FAILED,
                model_name=None,
                error=str(e),
                completed_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True) -> APIModelCollection:
        attempt_call(self.name)
        try:
            models = []
            
            # Consultar somente se pelo menos um tipo for solicitado
            if not (list_trained_models or list_base_models):
                return models
            
            # Modelos de consulta da API com base em parâmetros
            config_obj = google_types.ListModelsConfig(
                page_size=100,
                query_base=list_base_models,
            )
            
            pager = self.client.models.list(config=config_obj)
            
            for page in pager:
                for model in page:
                    # Determinar se o modelo é básico ou ajustado
                    is_base_model = not hasattr(model, 'tune_job') or not model.tune_job
                    
        except Exception as e:
            record_failure(self.name)
            logger.error(f"GeminiClient delete_file: {e}")
            raise APICommunicationError(f"Erro ao remover arquivo: {e}")

    def cancel_training(self, id: str) -> AISuccess:
        attempt_call(self.name)
        try:
            operation = self.client.tunings.cancel(name=id)
            record_success(self.name)
            return AISuccess(success=True)
        except Exception as e:
            record_failure(self.name)
            logger.error(f"GeminiClient cancel_training: {e}")
            return AISuccess(success=False, error=str(e))

@register_ai_client
class AnthropicClient(APIClient):
    """Cliente para interação com a API do Anthropic (Claude 3)."""
    name = "Anthropic"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            logger.error(f"{self.__class__.__name__}.__init__: Erro ao inicializar cliente Anthropic: {e}")
            raise APICommunicationError(f"Erro ao inicializar cliente Anthropic: {e}")

    def _call_api(self, message: AIMessage) -> AIComparisonResponse:
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            request_config = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": message.user_message}],
                **self.configurations
            }
            
            if 'max_tokens' not in request_config:
                request_config['max_tokens'] = 1024

            if 'stream' not in request_config:
                request_config['stream'] = False

            if message.system_message.strip():
                request_config['system'] = message.system_message
            
            response = self.client.messages.create(**request_config)
            if not response or not response.content or not response.content[0].text:
                raise APICommunicationError("Nenhuma mensagem retornada de Anthropic.")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            record_success(self.name)
            
            return AIComparisonResponse(
                response=response.content[0].text,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationError as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=str(e)
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"AnthropicClient _call_api: {e}")
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=f"Erro ao comunicar com Anthropic: {e}"
            )

@register_ai_client
class PerplexityClient(APIClient):
    """Cliente para interação com a API da Perplexity."""
    name = "Perplexity"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)

    def _call_api(self, message: AIMessage) -> AIComparisonResponse:
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            url = self.api_url if self.api_url else "https://api.perplexity.ai/chat/completions"
            messages = []
            if message.system_message.strip():
                messages.append({"role": "system", "content": message.system_message})
            messages.append({"role": "user", "content": message.user_message})
            
            request_config = {
                "model": self.model_name,
                "messages": messages,
                **self.configurations
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=request_config, headers=headers)
            if response.status_code != 200:
                raise APICommunicationError(f"API Perplexity retornou código {response.status_code}.")
                
            resp_json = response.json()
            generated_text = resp_json['choices'][0]['message'].get('content', '')
            if not generated_text:
                raise APICommunicationError("Nenhum texto retornado pela Perplexity.")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            record_success(self.name)
            
            return AIComparisonResponse(
                response=generated_text,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationError as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=str(e)
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"PerplexityClient _call_api: {e}")
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=f"Erro Perplexity: {e}"
            )

@register_ai_client
class LlamaClient(APIClient):
    """Cliente para interação com a API do Llama."""
    name = "Llama"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        self.client = LlamaAPI(self.api_key)

    def _call_api(self, message: AIMessage) -> AIComparisonResponse:
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            messages = []
            if message.system_message.strip():
                messages.append({"role": "system", "content": message.system_message})
            messages.append({"role": "user", "content": message.user_message})
            
            request_config = {
                "model": self.model_name,
                "messages": messages,
                "stream": self.configurations.get('stream', False),
                **self.configurations
            }
            
            logger.debug(f"[{self.name}] Enviando requisição para a API Llama")
            response = self.client.run(request_config)
            if not response:
                logger.warning(f"[{self.name}] A API retornou uma resposta vazia")
                raise APICommunicationError(f"[{self.name}] Nenhum texto retornado de Llama.")
            
            response_json = response.json()
            if "choices" not in response_json:
                error_str = ""
                if isinstance(response_json, list):
                    if response_json and isinstance(response_json[0], dict):
                        error_str = response_json[0].get('error', f'[{self.name}] Erro não especificado')
                    else:
                        error_str = f"[{self.name}] Resposta inesperada: {response_json}"
                elif isinstance(response_json, dict):
                    error_str = response_json.get('detail', response_json.get('error', f'[{self.name}] Erro não especificado'))
                else:
                    error_str = f"[{self.name}] Formato de resposta desconhecido: {response_json}"
                logger.error(f"[{self.name}] Erro na API: {error_str}")
                raise APICommunicationError(error_str)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            record_success(self.name)
            logger.debug(f"[{self.name}] Resposta recebida com sucesso")
            
            return AIComparisonResponse(
                response=response_json["choices"][0]["message"]["content"],
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationError as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=str(e)
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] _call_api: {e}")
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=f"[{self.name}] Erro: {e}"
            )

@register_ai_client
class AzureOpenAIClient(OpenAiClient):
    """
    Cliente para interação com a API do Azure OpenAI.
    Herda a maior parte da lógica do OpenAiClient.
    """
    name = "AzureOpenAI"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
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

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        self.client = ChatCompletionsClient(
            endpoint=self.api_url,
            credential=AzureKeyCredential(self.api_key),
        )

    def _call_api(self, message: AIMessage) -> AIComparisonResponse:
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            messages = []
            if message.system_message.strip():
                messages.append({"role": "system", "content": message.system_message})
            messages.append({"role": "user", "content": message.user_message})
            
            request_config = {
                "messages": messages,
                **self.configurations
            }
            
            response = self.client.complete(**request_config)
            if not response or not hasattr(response, 'choices') or not response.choices:
                raise APICommunicationError("Resposta inválida da Azure API")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            record_success(self.name)
            
            return AIComparisonResponse(
                response=response.choices[0].message.content,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationError as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=str(e)
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"AzureClient _call_api: {e}")
            return AIComparisonResponse(
                response="",
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=f"Erro Azure: {e}"
            )