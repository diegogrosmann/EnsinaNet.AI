"""
Módulo de visualizações (views) para a aplicação ai_config.

Este pacote contém as views organizadas por funcionalidade:
- ai_client: Gerenciamento de configurações de IA
- token: Configuração de tokens e vinculação com IAs
- training: Gerenciamento de treinamento de modelos
- training_files: Operações de arquivos de treinamento
- training_capture: Captura de exemplos de treinamento
"""

import logging

logger = logging.getLogger(__name__)
logger.debug("Inicializando módulo de views da aplicação ai_config")

from .ai_client import (
    manage_ai,
    create_ai,
    edit_ai,
    delete_ai,
    ai_available_tokens,
    ai_link_token
)

from .token import (
    prompt_config,
    token_ai_link,
)

from .training import (
    training_center,
    training_ai,
    training_monitor,
    training_cancel,
    training_delete
)

from .training_files import (
    training_file_create,
    training_file_upload,
    training_file_download,
    training_file_delete
)

from .training_capture import (
    capture_toggle,
    capture_get_examples
)

__all__ = [
    'manage_ai',
    'create_ai',
    'edit_ai',
    'delete_ai',
    'ai_available_tokens',
    'ai_link_token',
    'prompt_config',
    'token_ai_link',
    'training_center',
    'training_ai',
    'training_monitor',
    'training_cancel',
    'training_delete',
    'training_file_create',
    'training_file_upload',
    'training_file_download',
    'training_file_delete',
    'capture_toggle',
    'capture_get_examples'
]

logger.info("Módulo de views da aplicação ai_config carregado com sucesso")