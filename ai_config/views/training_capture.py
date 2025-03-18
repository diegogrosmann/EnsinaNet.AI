"""
Views para captura de exemplos de treinamento.

Este módulo contém funções para ativar, desativar e gerenciar 
a captura de exemplos de interação para treinamento de modelos de IA.
"""

import logging
import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

from accounts.models import UserToken
from ai_config.models import AIClientConfiguration, TrainingCapture
from core.types.api_response import APPResponse
from core.types.training import AITrainingCaptureConfig, AITrainingExampleCollection

logger = logging.getLogger(__name__)

@login_required
@require_POST
def capture_toggle(request: HttpRequest) -> JsonResponse:
    """Ativa ou desativa a captura de exemplos de treinamento.
    
    Ativa/desativa a coleta automática de exemplos para treinamento de IA a partir
    das interações feitas através de um token específico.
    
    Args:
        request: Requisição HTTP com token e ai_client_config
    
    Returns:
        JsonResponse: Status da operação com mensagem e código HTTP apropriado.
    """
    if request.method != 'POST':
        response = APPResponse(
            success=False,
            error='Método não permitido'
        )
        return JsonResponse(response.to_dict(), status=405)
        
    data = request.POST
    action = data.get('action', '')
    
    # Determinar se está ativando ou desativando com base na ação
    is_active = action == 'activate'
    
    if is_active:
        # Se estamos ativando, precisamos de token e ai_client_config
        token_id = data.get('token')
        ai_config_id = data.get('ai_client_config')
        
        if not token_id or not ai_config_id:
            response = APPResponse(
                success=False,
                error='Token e configuração de IA são obrigatórios para ativação'
            )
            return JsonResponse(response.to_dict(), status=400)
    else:
        # Se estamos desativando, não precisamos dos IDs específicos
        # pois o frontend já sabe qual é a captura ativa
        token_id = None
        ai_config_id = None
    
    try:
        with transaction.atomic():
            if is_active:
                # Verificar se o token existe antes de tentar buscá-lo
                try:
                    token = UserToken.objects.get(id=token_id, user=request.user)
                except UserToken.DoesNotExist:
                    logger.error(f"Token {token_id} não encontrado para o usuário {request.user.email}")
                    response = APPResponse(
                        success=False,
                        error='Token não encontrado'
                    )
                    return JsonResponse(response.to_dict(), status=404)
                
                try:
                    ai_config = AIClientConfiguration.objects.get(id=ai_config_id, user=request.user)
                except AIClientConfiguration.DoesNotExist:
                    response = APPResponse(
                        success=False,
                        error='Configuração de IA não encontrada.'
                    )
                    return JsonResponse(response.to_dict(), status=404)
                
                # Desativa qualquer captura ativa existente para este usuário
                TrainingCapture.objects.filter(token__user=request.user).update(is_active=False)
                
                # Obtém ou cria o objeto de captura
                capture, created = TrainingCapture.objects.get_or_create(
                    token=token,
                    ai_client_config=ai_config,
                    defaults={'is_active': True}
                )
                
                capture.is_active = True
                capture.save()
                
                status = "ativada"
                logger.info(f"Captura {status} para token {token.name} com IA {ai_config.name}")
            else:
                # Desativa todas as capturas do usuário
                captures = TrainingCapture.objects.filter(token__user=request.user, is_active=True)
                for capture in captures:
                    capture.delete()
                    
                status = "desativada"
                logger.info(f"Todas as capturas foram desativadas para o usuário {request.user.email}")
                
                # Usa a primeira captura desativada (se houver) para retornar informações
                capture = captures.first()
            
            # Prepara resposta, verificando se temos uma captura para retornar dados
            if 'capture' in locals() and capture:
                
                capture_data = capture.to_data()
                
                response_data = {
                    'active': capture.is_active,
                    'config': capture_data.to_dict(),
                }
            else:
                response_data = {
                    'active': False,
                }
            
            response_data['message'] = f"Captura {status} com sucesso"
            
            response = APPResponse(
                success=True,
                data=response_data
            )
            return JsonResponse(response.to_dict())
            
    except Exception as e:
        logger.exception(f"Erro ao alternar captura: {e}")
        response = APPResponse(
            success=False,
            error=str(e)
        )
        return JsonResponse(response.to_dict(), status=500)

@login_required
def capture_get_examples(request: HttpRequest, token_id: str, ai_id: int) -> JsonResponse:
    """Retorna os exemplos de treinamento capturados para uma IA.
    
    Coleta exemplos do arquivo temporário da captura e limpa-o após leitura,
    permitindo que estes exemplos sejam carregados na interface do usuário.
    
    Args:
        request: Requisição HTTP
        token_id: ID do token
        ai_id: ID da configuração de IA
    
    Returns:
        JsonResponse: Lista de exemplos capturados ou mensagem de erro.
    """
    try:
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        
        try:
            # Verifica se existe uma captura para o token
            capture = TrainingCapture.objects.get(token=token, ai_client_config=ai_config)
            
            # Obter a coleção de exemplos
            collection = capture.file_data

            # Limpa a coleção após leitura
            capture.file_data =  AITrainingExampleCollection()
            capture.save()
                
            logger.info(f"Retornados {len(collection.examples)} exemplos para token {token.name}")
            response = APPResponse(
                success=True,
                data={
                    'examples': collection.to_dict(),
                    'count': len(collection.examples),
                }
            )
            return JsonResponse(response.to_dict())
            
        except TrainingCapture.DoesNotExist:
            response = APPResponse(
                success=True, 
                data={
                    'examples': [], 
                    'count': 0,
                    'message': 'Não há captura configurada para este token.'
                }
            )
            return JsonResponse(response.to_dict())
            
    except UserToken.DoesNotExist:
        response = APPResponse(
            success=False,
            error='Token não encontrado.'
        )
        return JsonResponse(response.to_dict(), status=404)
    except AIClientConfiguration.DoesNotExist:
        response = APPResponse(
            success=False,
            error='Configuração de IA não encontrada.'
        )
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        logger.exception(f"Erro ao obter exemplos: {e}")
        response = APPResponse(
            success=False,
            error=str(e)
        )
        return JsonResponse(response.to_dict(), status=500)
