"""Middleware para monitoramento de requisições da API.

Este módulo implementa o monitoramento de uso da API, registrando métricas
como tempo de execução, dados do token e status das requisições.
"""

import logging
from typing import Optional
import time
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from accounts.models import UserToken
from api.models import APILog
from core.types import APILogData

logger = logging.getLogger(__name__)

class MonitoringMiddleware(MiddlewareMixin):
    """Middleware para monitoramento de requisições da API.
    
    Registra logs de uso da API, incluindo tempo de execução e dados do token.
    """

    def process_request(self, request: HttpRequest) -> None:
        """Marca o início do processamento da requisição.
        
        Args:
            request: Objeto de requisição HTTP.
        """
        request.start_time = time.time()
        logger.debug(f"Iniciando monitoramento: {request.method} {request.path}")

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Registra o log da requisição após seu processamento.
        
        Args:
            request: Objeto de requisição HTTP.
            response: Objeto de resposta HTTP.
            
        Returns:
            HttpResponse: Resposta processada.
        """
        try:
            if hasattr(request, 'start_time'):
                execution_time = time.time() - request.start_time
                user_token = self._get_token_from_request(request)
                user = user_token.user if user_token else None

                # Cria o objeto de log usando os tipos definidos
                log_data = APILogData(
                    id=0,  # será definido ao salvar no banco
                    user_token=user_token.key if user_token else None,
                    path=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    execution_time=execution_time,
                    timestamp=datetime.now()
                )
                
                # Salva no banco usando os dados estruturados
                APILog.objects.create(
                    user=user,
                    user_token=user_token,
                    path=log_data.path,
                    method=log_data.method,
                    status_code=log_data.status_code,
                    execution_time=log_data.execution_time
                )
                
                logger.info(
                    f"Requisição processada: {request.method} {request.path} "
                    f"[status={response.status_code}, tempo={execution_time:.3f}s]"
                )
        except Exception as e:
            logger.exception(f"Erro ao registrar log de monitoramento: {e}")

        return response

    def _get_token_from_request(self, request: HttpRequest) -> Optional[UserToken]:
        """Extrai e valida o token da requisição.
        
        Args:
            request: Objeto de requisição HTTP.
            
        Returns:
            Optional[UserToken]: Token encontrado ou None.
        """
        try:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header:
                return None
                
            token_key = auth_header.split(' ')[-1] if ' ' in auth_header else ''
            if not token_key:
                return None
                
            return UserToken.objects.get(key=token_key)
        except UserToken.DoesNotExist:
            logger.warning(f"Token inválido detectado")
            return None
        except Exception as e:
            logger.error(f"Erro ao processar token: {e}")
            return None
