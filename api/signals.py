"""
Sinais para aplicação da API.

Este módulo contém os sinais Django utilizados pela aplicação API,
permitindo a execução de código em resposta a eventos específicos
do modelo de dados e do ciclo de vida da aplicação.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from typing import Any, Dict, Type, Optional
from django.db.models import Model

from core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

# Dicionário para rastrear sinais registrados
_registered_signals: Dict[str, int] = {}

def register_signal(model: Type[Model], signal_type: str, handler: Any) -> None:
    """Registra um sinal para um modelo específico.
    
    Esta função auxiliar registra um manipulador de sinal para um modelo
    e mantém um registro dos sinais registrados.
    
    Args:
        model: Classe do modelo para registrar o sinal.
        signal_type: Tipo de sinal ('post_save', 'post_delete', etc).
        handler: Função manipuladora do sinal.
        
    Raises:
        ApplicationError: Se ocorrer erro no registro do sinal.
    """
    try:
        signal_obj = None
        if signal_type == 'post_save':
            signal_obj = post_save
        elif signal_type == 'post_delete':
            signal_obj = post_delete
        else:
            logger.warning(f"Tipo de sinal desconhecido: {signal_type}")
            return
            
        signal_obj.connect(handler, sender=model)
        key = f"{model.__name__}_{signal_type}"
        _registered_signals[key] = _registered_signals.get(key, 0) + 1
        
        logger.debug(f"Sinal registrado: {signal_type} para {model.__name__}")
    except Exception as e:
        logger.error(f"Erro ao registrar sinal {signal_type} para {model.__name__}: {str(e)}")
        raise ApplicationError(f"Falha ao configurar sinal: {str(e)}")

def get_registered_signals() -> Dict[str, int]:
    """Retorna um dicionário de sinais registrados.
    
    Returns:
        Dict[str, int]: Mapeamento de sinais para contagem de registros.
    """
    return _registered_signals.copy()

logger.info("Módulo de sinais da API inicializado")
# Mais sinais podem ser adicionados conforme necessário
