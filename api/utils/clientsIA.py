"""Clientes para diferentes APIs de IA."""
from datetime import datetime, time
from typing import Any, Dict, List, Optional, TypeVar, Union
from dataclasses import dataclass

from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, TypeVar, Union
from dataclasses import dataclass
import uuid

import anthropic
from google import genai
from google.genai import types
import requests

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from llamaapi import LlamaAPI
from openai import AzureOpenAI, OpenAI


# Imports necessários adicionados
import html
import json
import logging
import os
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
from openai.types import FileObject
from openai.types.fine_tuning import FineTuningJob

from core.types import (
    AIClientConfig,
    TrainingStatus,
    AITrainingData as TrainingResult
)
from core.exceptions import APICommunicationError, MissingAPIKeyError
from django.template import engines
from api.utils.circuit_breaker import (
    attempt_call,
    record_failure, 
    record_success,
    CircuitOpenError
)

# Configuração
logger = logging.getLogger(__name__)
load_dotenv()

# Tipos
T = TypeVar('T')
AI_CLIENT_MAPPING: Dict[str, type] = {}

# Remover as definições duplicadas de TrainingStatus e TrainingResult aqui

def register_ai_client(cls: type) -> type:
    """Registra uma classe de cliente de IA no mapeamento global.
    
    Args:
        cls: Classe do cliente a ser registrada

    Returns:
        A mesma classe, permitindo uso como decorador
    """
    AI_CLIENT_MAPPING[cls.name] = cls
    logger.debug(f"Cliente de IA registrado: {cls.name}")
    return cls

class APIClient:
    """Classe base abstrata para implementação de clientes de IA.
    
    Define a interface comum e funcionalidades básicas que todos os
    clientes de IA devem implementar.
    
    Attributes:
        name: Nome identificador do cliente
        can_train: Se suporta treinamento
        supports_system_message: Se aceita mensagem do sistema
        api_key: Chave de API para autenticação
        api_url: URL base da API (opcional)
        model_name: Nome/ID do modelo a ser usado
        configurations: Configurações específicas do cliente
        base_instruction: Instrução base para prompts
        prompt: Template de prompt personalizado
        responses: Template de respostas
        use_system_message: Se deve usar mensagem do sistema
    """
    
    name = ''
    can_train = False
    supports_system_message = True

    def __init__(self, config: AIClientConfig):
        """Inicializa um novo cliente de IA.
        
        Args:
            config: Configurações necessárias para o cliente
            
        Raises:
            MissingAPIKeyError: Se api_key não fornecida
        """
        # Armazena a referência à configuração original
        self.config = config
        
        # Configura com base na nova estrutura de AIClientConfig
        self.api_key = config.ai_global_config.get('api_key')
        self.api_url = config.ai_global_config.get('api_url')
        
        # Extrair dados do ai_client_config
        self.model_name = config.ai_client_config.get('model_name', '')
        self.configurations = config.ai_client_config.get('configurations', {}).copy()
        self.training_configurations = config.ai_client_config.get('training_configurations', {}).copy()
        self.use_system_message = config.ai_client_config.get('use_system_message', True)
        
        # Propriedades de prompt a partir do dicionário prompt_config
        self.base_instruction = config.prompt_config.get('base_instruction', '')
        self.prompt = config.prompt_config.get('prompt', '')
        self.responses = config.prompt_config.get('responses', '')

        if not self.api_key:
            raise MissingAPIKeyError(f"{self.name}: Chave de API não configurada.")
        
        logger.debug(f"[{self.name}] {self.__class__.__name__}.__init__: Inicializado com configurações: "
                    f"{self.configurations}")

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Renderiza um template usando a engine Django.
        
        Args:
            template: Template em formato string
            context: Variáveis para renderização
            
        Returns:
            Template renderizado
            
        Raises:
            APICommunicationError: Se falhar ao renderizar
        """
        try:
            django_engine = engines['django']
            template_engine = django_engine.from_string(template)
            return template_engine.render(context)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao renderizar template: {e}")
            raise APICommunicationError(f"Erro ao processar template: {e}")

    def _prepare_prompts(self, **kwargs) -> Dict[str, str]:
        """Prepara os prompts para envio à API.
        
        Args:
            **kwargs: Variáveis para renderização dos templates
            
        Returns:
            Dict com 'base_instruction' e 'user_prompt'
            
        Raises:
            APICommunicationError: Se falhar ao preparar
        """
        try:
            kwargs['ai_name'] = self.name
            kwargs['answer_format'] = self.responses

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
            logger.error(f"[{self.name}] Erro ao preparar prompts: {e}")
            raise APICommunicationError(f"Erro ao preparar prompts: {e}")

    def compare(self, data: Dict[str, Any]) -> tuple:
        """Compara dados usando a API de IA.
        
        Esta é a interface principal usada pelos clientes.
        
        Args:
            data: Dados para comparação
            
        Returns:
            Tupla (resposta_ia, system_message, user_message)
            
        Raises:
            APICommunicationError: Se falhar ao comparar
        """
        try:
            logger.debug(f"[{self.name}] Iniciando comparação de dados")
            prompts = self._prepare_prompts(**data)
            system_message = prompts.get('base_instruction', '')
            user_message = prompts.get('user_prompt', '')

            # Implementando o retry aqui
            response = self._call_api(prompts=prompts)
        except Exception as e:
            logger.error(f"[{self.name}] Erro ao comparar dados: {e}")
            raise APICommunicationError(f"Erro na comparação: {e}")

        return (response, system_message, user_message)

    def _call_api(self, prompts: Dict[str, str]) -> str:
        """Método abstrato para chamar a API específica.
        
        Args:
            prompts: Dicionário com prompts preparados
            
        Returns:
            Resposta da API
            
        Raises:
            NotImplementedError: Se não implementado pela subclasse
        """
        raise NotImplementedError(
            f"[{self.name}] Subclasses devem implementar _call_api"
        )

    def _prepare_train(self, file_path: str) -> Any:
        """
        Prepara os dados para treinamento.
        Subclasses podem sobrescrever para formatar os dados.

        Args:
            file_path: Caminho do arquivo original.

        Returns:
            Any: Dados preparados no formato específico de cada IA.
        """
        logger.debug(f"[{self.name}] Preparando arquivo {file_path} para treinamento")
        return file_path

    def train(self, file_path: str) -> TrainingResult:
        """
        Prepara e inicia o treinamento.

        Args:
            file_path: Caminho do arquivo de treinamento.

        Returns:
            TrainingResult: Resultado inicial do treinamento com job_id.

        Raises:
            NotImplementedError: Se a IA não suportar treinamento.
        """
        if not self.can_train:
            logger.warning(f"[{self.name}] Tentativa de treinamento em cliente sem suporte a treinamento")
            raise NotImplementedError(f"[{self.name}] Este cliente não suporta treinamento.")

        # Prepara o arquivo de treinamento
        prepared_file_path = self._prepare_train(file_path)
        
        try:
            # Inicia o treinamento com o arquivo preparado
            return self._start_training(prepared_file_path)
        finally:
            # Limpa o arquivo temporário após o uso
            if prepared_file_path and prepared_file_path != file_path:
                try:
                    os.remove(prepared_file_path)
                except Exception as e:
                    logger.warning(f"[{self.name}] Erro ao remover arquivo temporário {prepared_file_path}: {e}")

    def _start_training(self, training_data: Any) -> TrainingResult:
        """
        Inicia o treinamento com os dados preparados.
        As subclasses devem implementar.

        Args:
            training_data: Dados preparados para treinamento (arquivo, objeto, etc).

        Returns:
            TrainingResult: Resultado inicial com job_id.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar _start_training")

    def get_training_status(self, job_id: str) -> TrainingResult:
        """
        Verifica o status atual do treinamento.

        Args:
            job_id: ID do job de treinamento.

        Returns:
            TrainingResult: Status atual do treinamento.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar get_training_status.")

    def _call_train_api(self, training_data: str) -> str:
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

    def list_trained_models(self) -> list:
        """
        Lista os modelos treinados disponíveis.

        Returns:
            list: Lista de modelos treinados.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar list_trained_models.")

    def cancel_training(self, id: str) -> bool:
        """
        Cancela um job de treinamento em andamento.

        Args:
            job_id (str): ID do job a ser cancelado.

        Returns:
            bool: True se cancelado com sucesso.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar cancel_training.")

    def delete_trained_model(self, model_name: str) -> bool:
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

    def list_files(self) -> list:
        """Lista todos os arquivos.

        Returns:
            list: Lista de arquivos.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(f"[{self.name}] Subclasses devem implementar list_training_files.")

    def delete_file(self, file_id: str) -> bool:
        """Remove um arquivo.

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
        Realiza a chamada direta à API do OpenAI.
        O retry agora é feito no método compare da classe base.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Conteúdo de resposta.

        Raises:
            APICommunicationError: Em caso de falha na comunicação.
        """
        logger.debug(f"[{self.name}] Iniciando chamada para OpenAI")

        attempt_call(self.name)
        try:
            # Verifica se existe a chave 'base_instruction'
            base_instruction = prompts.get('base_instruction', '').strip()

            # Monta o prompt final (se quisesse unificar system e user, mas aqui mantemos a lógica)
            final_prompt = base_instruction if base_instruction else ""
            messages = []
            if final_prompt.strip():
                messages.append({"role": "system", "content": final_prompt})
            messages.append({"role": "user", "content": prompts['user_prompt']})

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages

            response = self.client.chat.completions.create(**self.configurations)

            if not response:
                logger.error(f"{self.__class__.__name__}._call_api: Nenhuma mensagem retornada do OpenAI.")
                raise APICommunicationError("Nenhuma mensagem retornada do OpenAI.")

            if hasattr(response, 'choices') and response.choices:
                record_success(self.name)
                logger.debug(f"[{self.name}] Chamada concluída com sucesso")
                return response.choices[0].message.content
            else:
                logger.error(f"{self.__class__.__name__}._call_api: Resposta do OpenAI inválida: {response}")
                raise APICommunicationError("Resposta do OpenAI inválida.")
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"{self.__class__.__name__}._call_api: Erro ao comunicar com OpenAI: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

    def _prepare_train(self, file_path: str) -> str:
        """
        Prepara o arquivo para treinamento no formato JSONL da OpenAI.
        
        Args:
            file_path: Caminho do arquivo original JSON
            
        Returns:
            str: Caminho do arquivo JSONL formatado
        """
        try:
            # Lê o arquivo original
            with open(file_path, 'r') as f:
                training_data = json.load(f)

            # Cria arquivo temporário JSONL
            temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl')
            
            # Converte cada exemplo para o formato OpenAI
            for example in training_data:
                messages = []
                
                # Adiciona system message se existir
                if example.get('system_message'):
                    messages.append({
                        "role": "system",
                        "content": example['system_message']
                    })
                
                # Adiciona mensagem do usuário
                messages.append({
                    "role": "user",
                    "content": example['user_message']
                })
                
                # Adiciona resposta do assistente
                messages.append({
                    "role": "assistant",
                    "content": example['response']
                })
                
                # Escreve a linha no formato JSONL
                conversation = {"messages": messages}
                temp_file.write(json.dumps(conversation) + '\n')
            
            temp_file.close()
            return temp_file.name

        except Exception as e:
            logger.error(f"Erro ao preparar arquivo de treinamento: {e}")
            raise APICommunicationError(f"Erro ao preparar arquivo: {e}")

    def _start_training(self, training_data: Any) -> TrainingResult:
        """Inicia treinamento assíncrono na OpenAI.
        
        Args:
            training_data: Caminho do arquivo ou objeto com dados de treinamento.
        """
        attempt_call(self.name)
        try:
            # Upload do arquivo para OpenAI
            file_obj: FileObject = None
            with open(training_data, 'rb') as f:
                file_obj = self.client.files.create(file=f, purpose='fine-tune')
                        
            # Inicia o job de fine-tuning
            training_type = "supervised"
            training_params = {}
            
            if self.training_configurations:
                # Extrair o tipo se existir
                if 'type' in self.training_configurations:
                    training_type = self.training_configurations.pop('type')
                
                # Restante das configurações vai para hyperparameters
                training_params = self.training_configurations
            
            job: FineTuningJob = self.client.fine_tuning.jobs.create(
                training_file=file_obj.id,
                model=self.model_name,
                hyperparameters=training_params
            )

            record_success(self.name)
            return TrainingResult(
                job_id=job.id,
                status=TrainingStatus.IN_PROGRESS,
                details={'file_id': file_obj.id}
            )

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient _start_training: {e}")
            raise APICommunicationError(f"Erro ao iniciar treinamento: {e}")
        finally:
            # Remover arquivo temporário após uso
            try:
                import os
                if os.path.exists(training_data):
                    os.unlink(training_data)
            except Exception as e:
                logger.warning(f"Não foi possível remover arquivo temporário {training_data}: {e}")

    def get_training_status(self, job_id: str) -> TrainingResult:
        """Verifica status do treinamento na OpenAI."""
        attempt_call(self.name)
        
        try:
            status = self.client.fine_tuning.jobs.retrieve(job_id)
            
            if status.status == 'succeeded':
                return TrainingResult(
                    job_id=job_id,
                    status=TrainingStatus.COMPLETED,
                    model_name=status.fine_tuned_model,
                    completed_at=datetime.now(),
                    details=status,
                    progress=1.0
                )
            elif status.status == 'failed':
                return TrainingResult(
                    job_id=job_id,
                    status=TrainingStatus.FAILED,
                    error=getattr(status, 'error', 'Falha desconhecida'),
                    completed_at=datetime.now(),
                    details=status,
                    progress=status.trained_tokens / status.training_file_tokens if hasattr(status, 'trained_tokens') and hasattr(status, 'training_file_tokens') else 0
                )
            else:
                # Calcular o progresso se disponível
                progress = 0.0
                if hasattr(status, 'trained_tokens') and hasattr(status, 'training_file_tokens') and status.training_file_tokens > 0:
                    progress = status.trained_tokens / status.training_file_tokens
                
                return TrainingResult(
                    job_id=job_id,
                    status=TrainingStatus.IN_PROGRESS,
                    details=status,
                    progress=progress
                )

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient get_training_status: {e}")
            raise APICommunicationError(f"Erro ao verificar status: {e}")

    def _call_train_api(self, training_data: str) -> str:
        """
        Realiza o treinamento na API do OpenAI (exemplo de método síncrono).

        Args:
            training_data (str): Dados de treinamento em formato JSONL.

        Returns:
            str: Nome do modelo treinado.

        Raises:
            APICommunicationError: Em caso de erro no processo.
        """
        attempt_call(self.name)

        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl') as temp_file:
                temp_file.write(training_data)
                temp_file_path = temp_file.name

            with open(temp_file_path, 'rb') as f:
                ai_file = self.client.files.create(file=f, purpose='fine-tune')
            
            job = self.client.fine_tuning.jobs.create(
                training_file=ai_file.id,
                model=self.model_name,
                hyperparameters=self.configurations
            )

            # Monitora o status do treinamento
            while True:
                status = self.client.fine_tuning.jobs.retrieve(job.id)
                if status.status == 'succeeded':
                    record_success(self.name)
                    return status.fine_tuned_model
                elif status.status == 'failed':
                    raise APICommunicationError(f"Falha no treinamento: {status.error}")
                time.sleep(5)

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient train: Erro no treinamento: {e}")
            raise APICommunicationError(f"Erro ao treinar o modelo: {e}")

    def list_trained_models(self) -> list:
        """Lista os modelos treinados disponíveis.

        Returns:
            list: Lista de dicionários com informações dos modelos.
        """
        attempt_call(self.name)
        try:
            response = self.client.models.list()
            record_success(self.name)
            
            models = []
            for model in response.data:
                if model.id.startswith('ft:'):
                    models.append({
                        'name': model.id,
                        'created_at': datetime.fromtimestamp(model.created)
                    })
                
            return models
            
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient list_trained_models: {e}")
            raise APICommunicationError(f"Erro ao listar modelos: {e}")

    def cancel_training(self, job_id: str) -> bool:
        """
        Cancela um job de fine-tuning na OpenAI.

        Args:
            job_id (str): ID do job a ser cancelado.

        Returns:
            bool: True se cancelado com sucesso.
        """
        attempt_call(self.name)
        try:
            result = self.client.fine_tuning.jobs.cancel(job_id)
            record_success(self.name)
            return result.status == "cancelled"
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient cancel_training: {e}")
            raise APICommunicationError(f"Erro ao cancelar: {e}")

    def delete_trained_model(self, model_name: str) -> bool:
        """
        Remove um modelo fine-tuned da OpenAI.

        Args:
            model_name (str): Nome/ID do modelo a ser removido.

        Returns:
            bool: True se removido com sucesso.
        """
        attempt_call(self.name)
        try:
            result = self.client.models.delete(model_name)
            record_success(self.name)
            return result.deleted
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient delete_trained_model: {e}")
            raise APICommunicationError(f"Erro ao remover modelo: {e}")

    def list_files(self) -> list:
        """Lista todos os arquivos da OpenAI.

        Returns:
            list: Lista de arquivos.
        """
        attempt_call(self.name)
        try:
            response = self.client.files.list()
            record_success(self.name)
            
            files = []
            for file in response.data:
                files.append({
                    'id': file.id,
                    'filename': file.filename,
                    'bytes': file.bytes,
                    'created_at': datetime.fromtimestamp(file.created_at),
                    'purpose': file.purpose
                })
            return files

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient list_training_files: {e}")
            raise APICommunicationError(f"Erro ao listar arquivos: {e}")

    def delete_file(self, file_id: str) -> bool:
        """Remove um arquivo da OpenAI.

        Args:
            file_id (str): ID do arquivo a ser removido.

        Returns:
            bool: True se removido com sucesso.
        """
        attempt_call(self.name)
        try:
            response = self.client.files.delete(file_id)
            record_success(self.name)
            return response.deleted

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"OpenAiClient delete_training_file: {e}")
            raise APICommunicationError(f"Erro ao remover arquivo: {e}")


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
        self.client = genai.Client(api_key=self.api_key)

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada direta à API do Gemini (sem retry aqui).
        O retry agora é feito no método compare da classe base.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }
            
        Returns:
            str: Texto gerado pela API
            
        Raises:
            APICommunicationError: Em caso de falha
        """
        attempt_call(self.name)
        logger.debug(f"[{self.name}] Iniciando chamada para Gemini")

        try:
            base_instruction = prompts.get('base_instruction', '').strip()
            if base_instruction:
                system_instruction = [
                    types.Part.from_text(text=base_instruction),
                ]
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    **self.configurations
                )
            else:
                config = types.GenerateContentConfig(**self.configurations)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompts['user_prompt'],
                config=config
            )
            record_success(self.name)
            logger.debug(f"[{self.name}] Chamada concluída com sucesso")
            return response.text

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient _call_api: Erro ao comunicar com Gemini: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API: {e}")

    def _prepare_train(self, file_path: str) -> types.TuningDataset:
        """
        Prepara os dados para treinamento no formato do Gemini usando TuningDataset.
        
        Args:
            file_path: Caminho do arquivo JSON com dados de treinamento
            
        Returns:
            types.TuningDataset: Objeto TuningDataset com exemplos formatados
        """
        try:
            with open(file_path, 'r') as f:
                training_data = json.load(f)

            examples = []
            for item in training_data:
                text_input = item['user_message']
                if item.get('system_message'):
                    text_input = f"{item['system_message']}\n {text_input}"
                
                examples.append(
                    types.TuningExample(
                        text_input=text_input,
                        output=item['response']
                    )
                )
            
            return types.TuningDataset(examples=examples)

        except Exception as e:
            logger.error(f"GeminiClient _prepare_train: Erro ao preparar dados: {e}")
            raise APICommunicationError(f"Erro ao preparar dados de treinamento: {e}")

    def _start_training(self, training_data: str) -> TrainingResult:
        """Inicia o treinamento no Gemini."""
        attempt_call(self.name)
        try:
            if 'tuned_model_display_name' not in self.training_configurations:
                random_suffix = uuid.uuid4().hex[:8]
                display_name = f"{self.model_name}-Tuned-{random_suffix}"
                display_name = display_name[:40]
                self.training_configurations['tuned_model_display_name'] = display_name

            config=types.CreateTuningJobConfig(
                **self.training_configurations
            )

            tuning_job = self.client.tunings.tune(
                base_model=self.model_name if '/' in self.model_name else f'models/{self.model_name}',
                training_dataset=training_data,
                config=config
            )

            record_success(self.name)
            return TrainingResult(
                job_id=tuning_job.name,
                status=TrainingStatus.IN_PROGRESS,
                details=tuning_job
            )

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient _start_training: {e}")
            raise APICommunicationError(f"Erro ao iniciar treinamento: {e}")

    def get_training_status(self, job_id: str) -> TrainingResult:
        try:
            # Obtém a operação pelo ID do job
            operation = self.client.tunings.get(
                name=job_id
            )
            if operation.has_ended:
                if operation.has_succeeded:
                    return TrainingResult(
                        job_id=job_id,
                        status=TrainingStatus.COMPLETED,
                        model_name=operation.name,
                        completed_at=operation.end_time,
                        progress=1.0
                    )    
                else:
                    return TrainingResult(
                        job_id=job_id,
                        status=TrainingStatus.FAILED,
                        error=str(operation.error),
                        completed_at=datetime.now(),
                        progress=1.0
                    )
            else:               
                return TrainingResult(
                    job_id=job_id,
                    status=TrainingStatus.IN_PROGRESS,
                    progress=0
                )

        except Exception as e:
            # Trata qualquer exceção durante o processo
            return TrainingResult(
                job_id=job_id,
                status=TrainingStatus.FAILED,
                error=str(e),
                completed_at=datetime.now(),
                progress=0.0
            )

    def _list_models(self, query_base: bool = True)-> list[str]:
        """Lista todos os modelos disponíveis no Gemini."""
        attempt_call(self.name)
        try:
            config = types.ListModelsConfig(
                page_size=10,
                query_base=query_base,   # True => base models, False => tuned models
            )

            pager = self.client.models.list(config=config)

            nomes_modelos = []
            for page in pager:
                for model in page:
                    nomes_modelos.append(model.name)
            
            return nomes_modelos

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient list_trained_models: {e}")
            raise APICommunicationError(f"Erro ao listar modelos: {e}")

    def list_trained_models(self) -> list:
        """Lista os modelos treinados disponíveis no Gemini."""
        return self._list_models(False)

    def delete_trained_model(self, model_name: str) -> bool:
        """
        Remove um modelo treinado do Gemini.

        Args:
            model_name (str): Nome/ID do modelo a ser removido.

        Returns:
            bool: True se removido com sucesso.
        """
        attempt_call(self.name)
        try:
            self.client.models.delete(model_name)
            record_success(self.name)
            return True

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient delete_trained_model: {e}")
            raise APICommunicationError(f"Erro ao remover modelo: {e}")

    def list_files(self) -> list:
        """Lista todos os arquivos disponíveis no Gemini."""
        attempt_call(self.name)
        try:
            files = []
            pager = self.client.files.list(config={'page_size': 10})
            for page in pager:
                for file in page:
                    files.append({
                        'id': file.name,
                        'filename': file.display_name,
                        'created_at': datetime.fromtimestamp(file.create_time)
                    })
            record_success(self.name)
            return files
        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient list_files: {e}")
            raise APICommunicationError(f"Erro ao listar arquivos: {e}")
        
    def delete_file(self, file_id: str) -> bool:
        """Remove um arquivo do Gemini."""
        attempt_call(self.name)
        try:
            self.client.files.delete(name=file_id)
            record_success(self.name)
            return True

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"GeminiClient delete_file: {e}")
            raise APICommunicationError(f"Erro ao remover arquivo: {e}")


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
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            logger.error(f"{self.__class__.__name__}.__init__: Erro ao inicializar cliente Anthropic: {e}")
            raise APICommunicationError(f"Erro ao inicializar cliente Anthropic: {e}")

    def _call_api(self, prompts: dict) -> str:
        """
        Realiza a chamada direta à API do Claude 3 (sem retry aqui).
        O retry agora é feito no método compare da classe base.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Texto de resposta do Claude.

        Raises:
            APICommunicationError: Em caso de falha de rede ou resposta inválida.
        """
        attempt_call(self.name)
        try:
            system = prompts.get('base_instruction', '')
            user_prompt = prompts.get('user_prompt', '')

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
        Realiza a chamada direta à API da Perplexity (sem retry aqui).
        O retry agora é feito no método compare da classe base.

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

            base_instruction = prompts.get('base_instruction', '').strip()
            messages = []
            if base_instruction:
                messages.append({"role": "system", "content": base_instruction})
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
        Realiza a chamada direta à API do Llama (sem retry aqui).
        O retry agora é feito no método compare da classe base.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Conteúdo retornado pela API do Llama.

        Raises:
            APICommunicationError: Se ocorrer erro na comunicação.
        """
        attempt_call(self.name)
        try:
            base_instruction = prompts.get('base_instruction', '').strip()
            user_prompt = prompts.get('user_prompt', '')

            messages = []
            if base_instruction:
                messages.append({"role": "system", "content": base_instruction})
            messages.append({"role": "user", "content": user_prompt})

            self.configurations['model'] = self.model_name
            self.configurations['messages'] = messages
            self.configurations['stream'] = self.configurations.get('stream', False)

            logger.debug(f"[{self.name}] Enviando requisição para a API Llama")
            response = self.client.run(self.configurations)

            if not response:
                logger.warning(f"[{self.name}] A API retornou uma resposta vazia")
                raise APICommunicationError(f"[{self.name}] Nenhum texto retornado de Llama.")

            response_json = response.json()
            
            if "choices" not in response_json:
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

            record_success(self.name)
            logger.debug(f"[{self.name}] Resposta recebida com sucesso")
            return response_json["choices"][0]["message"]["content"]

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"[{self.name}] _call_api: {e}")
            raise APICommunicationError(f"[{self.name}] Erro: {e}")


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
        Realiza a chamada direta à API do Azure (sem retry aqui).
        O retry agora é feito no método compare da classe base.

        Args:
            prompts (dict): { 'base_instruction': X, 'user_prompt': Y }.

        Returns:
            str: Conteúdo retornado.

        Raises:
            APICommunicationError: Se não houver resposta válida.
        """
        attempt_call(self.name)
        try:
            base_instruction = prompts.get('base_instruction', '').strip()
            user_prompt = prompts.get('user_prompt', '')

            messages = []
            if base_instruction:
                messages.append({"role": "system", "content": base_instruction})
            messages.append({"role": "user", "content": user_prompt})

            self.configurations['messages'] = messages
            response = self.client.complete(**self.configurations)

            if not response or not hasattr(response, 'choices') or not response.choices:
                raise APICommunicationError("Resposta inválida da Azure API")

            record_success(self.name)
            return response.choices[0].message.content

        except Exception as e:
            record_failure(self.name)
            if isinstance(e, CircuitOpenError):
                raise e
            logger.error(f"AzureClient _call_api: {e}")
            raise APICommunicationError(f"Erro Azure: {e}")
