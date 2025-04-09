"""
Clientes para diferentes APIs de IA.

Este módulo define a interface base e as implementações específicas para a comunicação com
diversas APIs de IA. A documentação segue o padrão Google e os tratamentos de exceção utilizam
exceções centralizadas para uniformizar os erros.
"""

from datetime import datetime
import io
import json
import os
from typing import Any, Dict, TypeVar, Tuple
import uuid
import anthropic
from google import genai
from google.genai import types as google_types
import requests
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from llamaapi import LlamaAPI
from openai import AsyncOpenAI, AzureOpenAI, OpenAI
from openai.types import FileObject
from openai.types.fine_tuning import FineTuningJob
import html
import logging
from dotenv import load_dotenv

from api.exceptions import (
    APICommunicationException, 
    MissingAPIKeyException
)

from core.types import (
    AIConfig,
    AIResponse, 
    AIPrompt,
    SingleComparisonRequestData, 
    AIFile, 
    TrainingResponse,
    JSONDict,
    APIError
)

from django.template import engines
from api.utils.circuit_breaker import (
    attempt_call,
    record_failure,
    record_success,
)
from core.types.ai import AIExampleDict, AIResult
from core.types.api import APIFile, APIFileCollection, APIModel, APIModelCollection
from core.types.status import EntityStatus

# Configuração do logger e carregamento do .env
logger = logging.getLogger(__name__)
load_dotenv()

# Tipos
T = TypeVar('T')
AI_CLIENT_MAPPING: Dict[str, type] = {}

def register_ai_client(cls: type) -> type:
    """Registra uma classe de cliente de IA no mapeamento global.

    Args:
        cls (type): Classe do cliente a ser registrada.

    Returns:
        type: A mesma classe, permitindo seu uso como decorador.
    """
    AI_CLIENT_MAPPING[cls.name] = cls
    logger.debug(f"Cliente de IA registrado: {cls.name}")
    return cls


class APIClient:
    """Classe base abstrata para implementação de clientes de IA.

    Define a interface comum e funcionalidades básicas que todos os clientes de IA devem implementar.

    Atributos:
        name (str): Nome identificador do cliente.
        can_train (bool): Indica se o cliente suporta treinamento.
        supports_system_message (bool): Indica se o cliente aceita mensagem do sistema.
    """

    name = ''
    can_train = False
    supports_system_message = True

    def __init__(self, config: AIConfig) -> None:
        """Inicializa o cliente com as configurações de IA.

        Args:
            config (AIConfig): Configuração da API de IA.

        Raises:
            MissingAPIKeyException: Se a chave de API não estiver configurada.
        """
        # Configura atributos básicos
        self.api_key = config.api_key
        self.api_url = config.api_url
        self.model_name = config.model_name or ''
        self.configurations = config.configurations or {}
        self.use_system_message = config.use_system_message
        self.training_configurations = config.training_configurations or {}

        # Configura dados de prompt diretamente dos campos de config
        self.base_instruction = config.base_instruction or ''
        self.prompt = config.prompt or ''
        self.responses = config.responses or ''

        if not self.api_key:
            raise MissingAPIKeyException(f"{self.name}: Chave de API não configurada.")

        logger.debug(f"[{self.name}] {self.__class__.__name__}.__init__: Inicializado com configurações: {self.configurations}")

    def _render_template(self, template: str, context: JSONDict) -> str:
        """Renderiza um template utilizando a engine Django.

        Args:
            template (str): Template em formato de string.
            context (JSONDict): Dicionário com variáveis para renderização.

        Returns:
            str: Template renderizado.

        Raises:
            APICommunicationException: Se ocorrer erro na renderização.
        """
        try:
            django_engine = engines['django']
            template_engine = django_engine.from_string(template)
            return template_engine.render(context)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao renderizar template: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao processar template: {e}")

    def _prepare_prompts(self, data: SingleComparisonRequestData) -> AIPrompt:
        """Prepara os prompts para envio à API.

        Args:
            data (SingleComparisonRequestData): Dados para comparação.

        Returns:
            AIPrompt: Objeto contendo 'system_message' e 'user_message' preparados.

        Raises:
            APICommunicationException: Se ocorrer erro na preparação dos prompts.
        """
        try:
            data_dict = data.__dict__ if hasattr(data, '__dict__') else data._asdict()
            data_dict['ai_name'] = self.name
            data_dict['answer_format'] = self.responses

            base_instruction = html.unescape(self._render_template(self.base_instruction, data_dict))
            prompt = html.unescape(self._render_template(self.prompt, data_dict))

            if self.use_system_message and self.supports_system_message:
                return AIPrompt(
                    system_message=base_instruction,
                    user_message=prompt
                )
            else:
                combined_prompt = (base_instruction + "\n" + prompt).strip()
                return AIPrompt(
                    system_message='',
                    user_message=combined_prompt
                )
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao preparar prompts: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao preparar prompts: {e}")

    def compare(self, data: SingleComparisonRequestData) -> Tuple[AIResponse, AIPrompt]:
        """Compara dados utilizando a API de IA.

        Args:
            data (SingleComparisonRequestData): Dados para comparação.

        Returns:
            Tuple[AIResponse, AIPrompt]: Tupla contendo a resposta da API e os prompts utilizados.

        Raises:
            APICommunicationException: Se ocorrer erro durante a comparação.
        """
        try:
            logger.debug(f"[{self.name}] Iniciando comparação de dados")
            message = self._prepare_prompts(data)
            response = self._call_api(message)
            return (response, message)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao comparar dados: {e}", exc_info=True)
            raise APICommunicationException(f"Erro na comparação: {e}")

    def _call_api(self, prompts: AIPrompt) -> AIResponse:
        """Método abstrato para chamar a API específica.

        Args:
            prompts (AIPrompt): Objeto com os prompts preparados.

        Returns:
            AIResponse: Resposta da API com metadados.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _call_api")

    def _prepare_train(self, file: AIFile) -> Any:
        """Prepara os dados para treinamento no formato esperado pela API.

        Args:
            file (AIFile): Dados do arquivo de treinamento.

        Returns:
            Any: Dados preparados para treinamento.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _prepare_train")

    def train(self, file: AIFile) -> TrainingResponse:
        """Prepara e inicia o treinamento utilizando os dados do arquivo.

        Args:
            file (AIFile): Dados do arquivo de treinamento.

        Returns:
            TrainingResponse: Resultado inicial do treinamento com job_id.

        Raises:
            NotImplementedError: Se a IA não suportar treinamento.
        """
        if not self.can_train:
            logger.warning(f"[{self.name}] Tentativa de treinamento em cliente sem suporte a treinamento")
            raise NotImplementedError(f"[{self.name}] Este cliente não suporta treinamento.")

        prepared_file_data = self._prepare_train(file)
        return self._start_training(prepared_file_data)

    def _start_training(self, training_data: Any) -> TrainingResponse:
        """Método abstrato para iniciar o treinamento.

        Args:
            training_data (Any): Dados preparados para treinamento.

        Returns:
            TrainingResponse: Resultado inicial do treinamento.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _start_training")

    def get_training_status(self, job_id: str) -> TrainingResponse:
        """Verifica o status atual do treinamento.

        Args:
            job_id (str): ID do job de treinamento.

        Returns:
            TrainingResponse: Status atual do treinamento.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar get_training_status.")

    def _call_train_api(self, training_data: str) -> AIResponse:
        """Método abstrato para chamar a API de treinamento.

        Args:
            training_data (str): Dados de treinamento preparados.

        Returns:
            AIResponse: Objeto representando o modelo treinado.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar o método _call_train_api.")

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True) -> AIResponse:
        """Lista os modelos disponíveis na API.

        Args:
            list_trained_models (bool): Se True, inclui modelos fine-tuned.
            list_base_models (bool): Se True, inclui modelos base.

        Returns:
            APIModelCollection: Lista de modelos disponíveis.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar list_trained_models.")

    def cancel_training(self, id: str) -> AIResponse:
        """Cancela um job de treinamento em andamento.

        Args:
            id (str): ID do job a ser cancelado.

        Returns:
            AIResponse: Objeto indicando sucesso ou falha da operação.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar cancel_training.")

    def delete_trained_model(self, model_name: str) -> AIResponse:
        """Remove um modelo treinado.

        Args:
            model_name (str): Nome ou ID do modelo a ser removido.

        Returns:
            AIResponse: Objeto indicando sucesso ou falha da operação.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar delete_trained_model.")

    def api_list_files(self) -> AIResponse:
        """Lista todos os arquivos disponíveis na API.

        Returns:
            APIFileCollection: Lista de arquivos disponíveis.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar list_training_files.")

    def delete_file(self, file_id: str) -> AIResponse:
        """Remove um arquivo da API.

        Args:
            file_id (str): ID do arquivo a ser removido.

        Returns:
            AIResponse: Objeto indicando sucesso ou falha da operação.

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
        """Inicializa o cliente da OpenAI.

        Args:
            config (AIConfig): Configuração da API OpenAI.
        """
        super().__init__(config)
        args = {'api_key': self.api_key}
        if self.api_url is not None:
            args['base_url'] = self.api_url
        self.client = OpenAI(**args)
        self.async_client = AsyncOpenAI(**args)

    def _call_api(self, message: AIPrompt) -> AIResponse:
        """Realiza a chamada à API da OpenAI para comparação.

        Args:
            message (AIPrompt): Prompts preparados para a chamada.

        Returns:
            AIResponse: Resposta da API com metadados.
        """
        logger.debug(f"[{self.name}] Iniciando chamada para OpenAI")
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            msgs = []
            if message.system_message.strip():
                msgs.append({"role": "system", "content": message.system_message})
            msgs.append({"role": "user", "content": message.user_message})

            request_config = {
                "model": self.model_name,
                "messages": msgs,
                **self.configurations
            }
            response = self.client.chat.completions.create(**request_config)
            if not response:
                logger.error(f"[{self.name}] _call_api: Nenhuma mensagem retornada do OpenAI.", exc_info=True)
                error = APIError(
                    message="Nenhuma mensagem retornada do OpenAI.",
                    endpoint="chat/completions",
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=0.0
                )

            processing_time = (datetime.now() - start_time).total_seconds()

            if hasattr(response, 'choices') and response.choices:
                record_success(self.name)
                logger.debug(f"[{self.name}] Chamada concluída com sucesso")
                reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)
                return AIResponse(
                    response=response.choices[0].message.content,
                    thinking=reasoning_content,
                    model_name=self.model_name,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
            else:
                logger.error(f"[{self.name}] _call_api: Resposta do OpenAI inválida: {response}", exc_info=True)
                error = APIError(
                    message="Resposta do OpenAI inválida.",
                    endpoint="chat/completions",
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
        except APICommunicationException as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            error = APIError(
                message=str(e),
                endpoint="chat/completions",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] _call_api: Erro ao comunicar com OpenAI: {e}", exc_info=True)
            error = APIError(
                message=str(e),
                endpoint="chat/completions",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )

    def _prepare_train(self, file: AIFile) -> Any:
        """Prepara os dados de treinamento no formato esperado pela API.

        Args:
            file (AIFile): Dicionário contendo exemplos de treinamento.

        Returns:
            Any: Dados preparados para treinamento.

        Raises:
            APICommunicationException: Se ocorrer erro durante o preparo dos dados.
        """
        try:
            # Usar file.data.items() como o Gemini faz
            training_data = file.data.items()
            jsonl_data = []
            for key, example in training_data:
                msgs = []
                if example.system_message:
                    msgs.append({
                        "role": "system",
                        "content": example.system_message.strip()
                    })
                msgs.append({
                    "role": "user",
                    "content": example.user_message.strip()
                })
                msgs.append({
                    "role": "assistant",
                    "content": example.response.strip()
                })
                conversation = {"messages": msgs}
                jsonl_data.append(json.dumps(conversation))
            return "\n".join(jsonl_data)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao preparar dados de treinamento: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao preparar dados: {e}")

    def _start_training(self, training_data: str) -> TrainingResponse:
        """Inicia o treinamento utilizando os dados preparados.

        Args:
            training_data (str): Dados de treinamento no formato JSONL.

        Returns:
            TrainingResponse: Resultado inicial do treinamento com job_id.
        """
        attempt_call(self.name)
        try:
            bytes_data = io.BytesIO(training_data.encode('utf-8'))
            bytes_data.name = 'training.jsonl'
            file_obj: FileObject = self.client.files.create(
                file=bytes_data,
                purpose='fine-tune'
            )
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
            return TrainingResponse(
                job_id=job.id,
                status=EntityStatus.IN_PROGRESS,
                model_name=None,
                error=None,
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] _start_training: {e}", exc_info=True)
            return TrainingResponse(
                job_id="",
                status=EntityStatus.FAILED,
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
                logger.warning(f"[{self.name}] Não foi possível remover arquivo temporário {training_data}: {e}", exc_info=True)

    def get_training_status(self, job_id: str) -> TrainingResponse:
        """Obtém o status atual do treinamento.

        Args:
            job_id (str): ID do job de treinamento.

        Returns:
            TrainingResponse: Status atual do treinamento.
        """
        attempt_call(self.name)
        try:
            status_obj = self.client.fine_tuning.jobs.retrieve(job_id)
            if status_obj.status == 'succeeded':
                return TrainingResponse(
                    job_id=job_id,
                    status=EntityStatus.COMPLETED,
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
                return TrainingResponse(
                    job_id=job_id,
                    status=EntityStatus.FAILED,
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
                return TrainingResponse(
                    job_id=job_id,
                    status=EntityStatus.IN_PROGRESS,
                    model_name=None,
                    error=None,
                    completed_at=None,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    progress=progress
                )
        except APICommunicationException:
            record_failure(self.name)
            raise
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] get_training_status: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao verificar status: {e}")

    def delete_trained_model(self, model_name: str) -> AIResult:
        """Remove um modelo treinado (fine-tuned) da OpenAI.

        Args:
            model_name (str): Nome ou ID do modelo a ser removido.

        Returns:
            AIResult: Objeto indicando sucesso ou falha da operação.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando remoção do modelo treinado: {model_name}")
            self.client.models.delete(model_name)
            record_success(self.name)
            logger.debug(f"[{self.name}] Modelo {model_name} removido com sucesso")
            return AIResult(success=True)
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] delete_trained_model: Erro ao remover modelo {model_name}: {e}", exc_info=True)
            return AIResult(success=False, error=str(e))

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True) -> APIModelCollection:
        """Lista os modelos disponíveis na API da OpenAI.

        Args:
            list_trained_models (bool): Se True, inclui modelos fine-tuned.
            list_base_models (bool): Se True, inclui modelos base.

        Returns:
            APIModelCollection: Lista de objetos APIModel.

        Raises:
            APICommunicationException: Se ocorrer erro ao listar os modelos.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando listagem de modelos")
            models_response = self.client.models.list()
            models_collection = []
            for model in models_response:
                is_fine_tuned = model.id.startswith('ft:') or ':' in model.id
                if (is_fine_tuned and list_trained_models) or (not is_fine_tuned and list_base_models):
                    models_collection.append(APIModel(
                        id=model.id,
                        name=model.id,
                        is_fine_tuned=is_fine_tuned
                    ))
            record_success(self.name)
            logger.debug(f"[{self.name}] Listagem de modelos concluída: {len(models_collection)} encontrados")
            return models_collection
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] api_list_models: Erro ao listar modelos: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao listar modelos: {e}")

    def api_list_files(self) -> APIFileCollection:
        """Lista todos os arquivos disponíveis na API da OpenAI.

        Returns:
            APIFileCollection: Lista de objetos APIFile.

        Raises:
            APICommunicationException: Se ocorrer erro na comunicação com a API.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando listagem de arquivos")
            files_response = self.client.files.list()
            files_collection = []
            for file in files_response.data:
                created_at = datetime.fromtimestamp(file.created_at)
                files_collection.append(APIFile(
                    id=file.id,
                    filename=file.filename,
                    bytes=file.bytes,
                    created_at=created_at
                ))
            record_success(self.name)
            logger.debug(f"[{self.name}] Listagem de arquivos concluída: {len(files_collection)} encontrados")
            return files_collection
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] api_list_files: Erro ao listar arquivos: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao listar arquivos")

    def delete_file(self, file_id: str) -> AIResult:
        """Remove um arquivo da API da OpenAI.

        Args:
            file_id (str): ID do arquivo a ser removido.

        Returns:
            AIResult: Objeto indicando sucesso ou falha da operação.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando remoção do arquivo: {file_id}")
            self.client.files.delete(file_id=file_id)
            record_success(self.name)
            logger.debug(f"[{self.name}] Arquivo {file_id} removido com sucesso")
            return AIResult(success=True)
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] delete_file: Erro ao remover arquivo {file_id}: {e}", exc_info=True)
            return AIResult(success=False, error=str(e))


@register_ai_client
class GeminiClient(APIClient):
    """Cliente para interação com a API do Google Gemini."""
    name = "Gemini"
    can_train = True

    def __init__(self, config: AIConfig) -> None:
        """Inicializa o cliente do Gemini.

        Args:
            config (AIConfig): Configuração da API Gemini.
        """
        super().__init__(config)
        self.client = genai.Client(api_key=self.api_key)

    def _call_api(self, message: AIPrompt) -> AIResponse:
        """Realiza a chamada à API do Gemini para comparação.

        Args:
            message (AIPrompt): Prompts preparados para a chamada.

        Returns:
            AIResponse: Resposta da API do Gemini.
        """
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
            return AIResponse(
                response=response.text,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Verificação se os atributos existem na exceção
            error_message = getattr(e, 'message', str(e))
            error_code = getattr(e, 'code', None)
            
            error = APIError(
                message=error_message,
                code=error_code,
                endpoint="generateContent",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time,
                error=error
            )

    def _prepare_train(self, file: AIFile) -> google_types.TuningDataset:
        """Prepara os dados de treinamento para o Gemini.

        Args:
            file (AIFile): Dados do arquivo de treinamento.

        Returns:
            google_types.TuningDataset: Dataset preparado para tuning.

        Raises:
            APICommunicationException: Se ocorrer erro na preparação dos dados.
        """
        try:
            training_data = file.data.items()
            examples = []
            for key, item in training_data: 
                text_input = item.user_message
                if item.system_message:
                    text_input = f"{item.system_message}\n {text_input}"
                examples.append(
                    google_types.TuningExample(
                        text_input=text_input,
                        output=item.response
                    )
                )
            return google_types.TuningDataset(examples=examples)
        except Exception as e:
            logger.error(f"[{self.name}] _prepare_train: Erro ao preparar dados: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao preparar dados de treinamento: {e}")

    def _start_training(self, training_data: Any) -> TrainingResponse:
        """Inicia o treinamento no Gemini.

        Args:
            training_data (Any): Dados de treinamento preparados.

        Returns:
            TrainingResponse: Resultado inicial do treinamento.
        """
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
            return TrainingResponse(
                job_id=tuning_job.name,
                status=EntityStatus.IN_PROGRESS,
                model_name=None,
                error=None,
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] _start_training: {e}", exc_info=True)
            return TrainingResponse(
                job_id="",
                status=EntityStatus.FAILED,
                model_name=None,
                error=str(e),
                completed_at=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )

    def get_training_status(self, job_id: str) -> TrainingResponse:
        """Obtém o status do treinamento no Gemini.

        Args:
            job_id (str): ID do job de treinamento.

        Returns:
            TrainingResponse: Status atual do treinamento.
        """
        attempt_call(self.name)
        try:
            operation = self.client.tunings.get(name=job_id)
            if operation.has_ended:
                if operation.has_succeeded:
                    return TrainingResponse(
                        job_id=job_id,
                        status=EntityStatus.COMPLETED,
                        model_name=operation.name,
                        error=None,
                        completed_at=operation.end_time,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        progress=1.0
                    )
                else:
                    return TrainingResponse(
                        job_id=job_id,
                        status=EntityStatus.FAILED,
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
                return TrainingResponse(
                    job_id=job_id,
                    status=EntityStatus.IN_PROGRESS,
                    model_name=None,
                    error=None,
                    completed_at=None,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    progress=progress
                )
        except APICommunicationException:
            record_failure(self.name)
            raise
        except Exception as e:
            logger.error(f"[{self.name}] get_training_status: {e}", exc_info=True)
            return TrainingResponse(
                job_id=job_id,
                status=EntityStatus.FAILED,
                model_name=None,
                error=str(e),
                completed_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                progress=0.0
            )

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True) -> APIModelCollection:
        """Lista os modelos disponíveis no Gemini.

        Args:
            list_trained_models (bool): Se True, inclui modelos fine-tuned.
            list_base_models (bool): Se True, inclui modelos base.

        Returns:
            APIModelCollection: Lista de objetos APIModel.

        Raises:
            APICommunicationException: Se ocorrer erro ao listar os modelos.
        """
        attempt_call(self.name)
        try:
            models = []
            if not (list_trained_models or list_base_models):
                return models

            def _process_model_pages(models_list, query_base):
                config_obj = google_types.ListModelsConfig(page_size=100, query_base=query_base)
                pager = self.client.models.list(config=config_obj)
                for page in pager:
                    models_list.append(APIModel(
                        id=page.name,
                        name=page.display_name or page.name,
                        is_fine_tuned=not query_base
                    ))
                return models_list

            if list_base_models:
                models = _process_model_pages(models, True)
            if list_trained_models:
                models = _process_model_pages(models, False)

            record_success(self.name)
            return models
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] list_trained_models: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao listar modelos: {e}")

    def delete_trained_model(self, model_name: str) -> AIResult:
        """Remove um modelo treinado no Gemini.

        Args:
            model_name (str): Nome ou ID completo do modelo a ser removido.

        Returns:
            AIResult: Objeto indicando sucesso ou falha da operação.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando remoção do modelo treinado: {model_name}")
            if not model_name.startswith('tunedModels/'):
                model_name = f'tunedModels/{model_name}'
            self.client.models.delete(model=model_name)
            record_success(self.name)
            logger.debug(f"[{self.name}] Modelo {model_name} removido com sucesso")
            return AIResult(success=True)
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] delete_trained_model: Erro ao remover modelo {model_name}: {e}", exc_info=True)
            return AIResult(success=False, error=str(e))

    def cancel_training(self, id: str) -> AIResult:
        """Cancela um job de treinamento em andamento no Gemini.

        Args:
            id (str): ID do job a ser cancelado.

        Returns:
            AIResult: Objeto indicando sucesso ou falha da operação.
        """
        attempt_call(self.name)
        try:
            operation = self.client.tunings.cancel(name=id)
            record_success(self.name)
            return AIResult(success=True)
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] cancel_training: {e}", exc_info=True)
            return AIResult(success=False, error=str(e))

    def api_list_files(self) -> APIFileCollection:
        """Lista todos os arquivos disponíveis na API do Gemini.

        Returns:
            APIFileCollection: Lista de objetos APIFile.

        Raises:
            APICommunicationException: Se ocorrer erro ao listar os arquivos.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando listagem de arquivos")
            config = google_types.ListFilesConfig(page_size=100)
            files_collection = []
            pager = self.client.files.list(config=config)
            for page in pager:
                for file in page:
                    files_collection.append(APIFile(
                        id=file.name.split('/')[-1] if file.name else str(uuid.uuid4()),
                        filename=file.display_name or os.path.basename(file.name) if file.name else "unknown",
                        bytes=file.size_bytes or 0,
                        created_at=datetime.fromisoformat(file.create_time.replace('Z', '+00:00')) if file.create_time else datetime.now()
                    ))
            record_success(self.name)
            logger.debug(f"[{self.name}] Listagem de arquivos concluída: {len(files_collection)} arquivos encontrados")
            return files_collection
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] api_list_files: Erro ao listar arquivos: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao listar arquivos: {e}")

    def delete_file(self, file_id: str) -> AIResult:
        """Remove um arquivo da API do Gemini.

        Args:
            file_id (str): ID do arquivo a ser removido.

        Returns:
            AIResult: Objeto indicando sucesso ou falha da operação.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando remoção do arquivo: {file_id}")
            if not file_id.startswith('files/'):
                file_name = f'files/{file_id}'
            else:
                file_name = file_id
            self.client.files.delete(name=file_name)
            record_success(self.name)
            logger.debug(f"[{self.name}] Arquivo {file_id} removido com sucesso")
            return AIResult(success=True)
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] delete_file: Erro ao remover arquivo {file_id}: {e}", exc_info=True)
            return AIResult(success=False, error=str(e))


@register_ai_client
class AnthropicClient(APIClient):
    """Cliente para interação com a API do Anthropic (Claude 3)."""
    name = "Anthropic"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
        """Inicializa o cliente do Anthropic.

        Args:
            config (AIConfig): Configuração da API Anthropic.

        Raises:
            APICommunicationException: Se ocorrer erro ao inicializar o cliente.
        """
        super().__init__(config)
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            logger.error(f"[{self.name}] __init__: Erro ao inicializar cliente Anthropic: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao inicializar cliente Anthropic: {e}")

    def _call_api(self, message: AIPrompt) -> AIResponse:
        """Realiza a chamada à API do Anthropic para comparação.

        Args:
            message (AIPrompt): Prompts preparados para a chamada.

        Returns:
            AIResponse: Resposta da API do Anthropic.
        """
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            request_config = {
                "model": self.model_name,
                "messages": [{
                    "role": "user", 
                    "content": [{
                        "type": "text",
                        "text": message.user_message
                    }]
                }],
                **self.configurations
            }
            if 'max_tokens' not in request_config:
                request_config['max_tokens'] = 1024
            if 'stream' not in request_config:
                request_config['stream'] = False
            if message.system_message.strip():
                request_config['system'] = message.system_message
            response = self.client.messages.create(**request_config)
            if not response or not response.content:
                error = APIError(
                    message="Nenhuma mensagem retornada de Anthropic.",
                    endpoint="messages",
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=0.0
                )
            
            extracted_text = ""
            extracted_thinking = ""
            for content_block in response.content:
                if content_block.type == "thinking":
                    extracted_thinking += content_block.thinking
                if content_block.type == "text":
                    extracted_text += content_block.text            
            processing_time = (datetime.now() - start_time).total_seconds()
            record_success(self.name)
            return AIResponse(
                response=extracted_text,
                thinking=extracted_thinking if extracted_thinking.strip() else None,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationException as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            error = APIError(
                message=str(e),
                endpoint="messages",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] _call_api: {e}", exc_info=True)
            error = APIError(
                message=str(e),
                endpoint="messages",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True) -> APIModelCollection:
        """Lista os modelos disponíveis na API do Anthropic.

        Args:
            list_trained_models (bool): Se True, inclui modelos fine-tuned (não aplicável para Anthropic).
            list_base_models (bool): Se True, inclui modelos base.

        Returns:
            APIModelCollection: Lista de objetos APIModel.

        Raises:
            APICommunicationException: Se ocorrer erro ao listar os modelos.
        """
        attempt_call(self.name)
        try:
            logger.debug(f"[{self.name}] Iniciando listagem de modelos")
            if not list_base_models:
                return []
            models_list_response = self.client.models.list()
            models_collection = []
            for model in models_list_response.data:
                models_collection.append(APIModel(
                    id=model.id,
                    name=model.display_name,
                    is_fine_tuned=False,
                ))
            record_success(self.name)
            logger.debug(f"[{self.name}] Listagem de modelos concluída: {len(models_collection)} modelos encontrados")
            return models_collection
        except Exception as e:
            record_failure(self.name)
            logger.error(f"[{self.name}] api_list_models: Erro ao listar modelos: {e}", exc_info=True)
            raise APICommunicationException(f"Erro ao listar modelos: {e}")


@register_ai_client
class PerplexityClient(APIClient):
    """Cliente para interação com a API da Perplexity."""
    name = "Perplexity"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
        """Inicializa o cliente da Perplexity.

        Args:
            config (AIConfig): Configuração da API Perplexity.
        """
        super().__init__(config)

    def _call_api(self, message: AIPrompt) -> AIResponse:
        """Realiza a chamada à API da Perplexity para comparação.

        Args:
            message (AIPrompt): Prompts preparados para a chamada.

        Returns:
            AIResponse: Resposta da API da Perplexity.
        """
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            url = self.api_url if self.api_url else "https://api.perplexity.ai/chat/completions"
            msgs = []
            if message.system_message.strip():
                msgs.append({"role": "system", "content": message.system_message})
            msgs.append({"role": "user", "content": message.user_message})
            request_config = {
                "model": self.model_name,
                "messages": msgs,
                **self.configurations
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=request_config, headers=headers)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if response.status_code != 200:
                error = APIError(
                    message=f"API Perplexity retornou código {response.status_code}.",
                    endpoint=url,
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
            resp_json = response.json()
            generated_text = resp_json['choices'][0]['message'].get('content', '')
            if not generated_text:
                error = APIError(
                    message="Nenhum texto retornado pela Perplexity.",
                    endpoint=url,
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
            record_success(self.name)
            return AIResponse(
                response=generated_text,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationException as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            error = APIError(
                message=str(e),
                endpoint="chat/completions",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] _call_api: {e}", exc_info=True)
            error = APIError(
                message=str(e),
                endpoint="chat/completions",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )


@register_ai_client
class LlamaClient(APIClient):
    """Cliente para interação com a API do Llama."""
    name = "Llama"
    can_train = False

    def __init__(self, config: AIConfig) -> None:
        """Inicializa o cliente do Llama.

        Args:
            config (AIConfig): Configuração da API Llama.
        """
        super().__init__(config)
        self.client = LlamaAPI(self.api_key)

    def _call_api(self, message: AIPrompt) -> AIResponse:
        """Realiza a chamada à API do Llama para comparação.

        Args:
            message (AIPrompt): Prompts preparados para a chamada.

        Returns:
            AIResponse: Resposta da API do Llama.
        """
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            msgs = []
            if message.system_message.strip():
                msgs.append({"role": "system", "content": message.system_message})
            msgs.append({"role": "user", "content": message.user_message})
            request_config = {
                "model": self.model_name,
                "messages": msgs,
                "stream": self.configurations.get('stream', False),
                **self.configurations
            }
            logger.debug(f"[{self.name}] Enviando requisição para a API Llama")
            response = self.client.run(request_config)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if not response:
                logger.warning(f"[{self.name}] A API retornou uma resposta vazia")
                error = APIError(
                    message=f"[{self.name}] Nenhum texto retornado de Llama.",
                    endpoint="run",
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
                
            response_json = response.json()
            if "choices" not in response_json:
                error_str = ""
                if isinstance(response_json, list):
                    if response_json and isinstance(response_json[0], dict):
                        error_str = response_json[0].get('error', f"[{self.name}] Erro não especificado")
                    else:
                        error_str = f"[{self.name}] Resposta inesperada: {response_json}"
                elif isinstance(response_json, dict):
                    error_str = response_json.get('detail', response_json.get('error', f"[{self.name}] Erro não especificado"))
                else:
                    error_str = f"[{self.name}] Formato de resposta desconhecido: {response_json}"
                logger.error(f"[{self.name}] Erro na API: {error_str}", exc_info=True)
                error = APIError(
                    message=error_str,
                    endpoint="run",
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
            record_success(self.name)
            logger.debug(f"[{self.name}] Resposta recebida com sucesso")
            return AIResponse(
                response=response_json["choices"][0]["message"]["content"],
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationException as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            error = APIError(
                message=str(e),
                endpoint="run",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] _call_api: {e}", exc_info=True)
            error = APIError(
                message=str(e),
                endpoint="run",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
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
        """Inicializa o cliente do Azure OpenAI.

        Args:
            config (AIConfig): Configuração da API Azure OpenAI.
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

    def __init__(self, config: AIConfig) -> None:
        """Inicializa o cliente do Azure.

        Args:
            config (AIConfig): Configuração da API Azure.
        """
        super().__init__(config)
        self.client = ChatCompletionsClient(
            endpoint=self.api_url,
            credential=AzureKeyCredential(self.api_key),
        )

    def _call_api(self, message: AIPrompt) -> AIResponse:
        """Realiza a chamada à API do Azure para comparação.

        Args:
            message (AIPrompt): Prompts preparados para a chamada.

        Returns:
            AIResponse: Resposta da API do Azure.
        """
        attempt_call(self.name)
        start_time = datetime.now()
        try:
            msgs = []
            if message.system_message.strip():
                msgs.append({"role": "system", "content": message.system_message})
            msgs.append({"role": "user", "content": message.user_message})
            request_config = {
                "messages": msgs,
                **self.configurations
            }
            response = self.client.complete(**request_config)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if not response or not hasattr(response, 'choices') or not response.choices:
                error = APIError(
                    message="Resposta inválida da Azure API",
                    endpoint="chat/completions",
                    resource=f"ai/{self.model_name}"
                )
                return AIResponse(
                    model_name=self.model_name,
                    error=error,
                    configurations=self.configurations,
                    processing_time=processing_time
                )
            record_success(self.name)
            return AIResponse(
                response=response.choices[0].message.content,
                model_name=self.model_name,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except APICommunicationException as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            error = APIError(
                message=str(e),
                endpoint="chat/completions",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )
        except Exception as e:
            record_failure(self.name)
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{self.name}] _call_api: {e}", exc_info=True)
            error = APIError(
                message=str(e),
                endpoint="chat/completions",
                resource=f"ai/{self.model_name}"
            )
            return AIResponse(
                model_name=self.model_name,
                error=error,
                configurations=self.configurations,
                processing_time=processing_time
            )
