<<<<<<< HEAD
"""
Views para captura de exemplos de treinamento.

Este módulo contém funções para ativar, desativar e gerenciar 
a captura de exemplos de interação para treinamento de modelos de IA.
"""

import logging
=======
import logging
import json
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST
<<<<<<< HEAD
from django.db import transaction

from accounts.models import UserToken
from ai_config.models import AIClientConfiguration, TrainingCapture
from core.types import APPResponse, APPError, AIExampleDict
=======

from accounts.models import UserToken
from ai_config.models import AIClientConfiguration, TrainingCapture
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)

logger = logging.getLogger(__name__)

@login_required
@require_POST
def capture_toggle(request: HttpRequest) -> JsonResponse:
<<<<<<< HEAD
    """Ativa ou desativa a captura de exemplos de treinamento.
    
    Ativa/desativa a coleta automática de exemplos para treinamento de IA a partir
    das interações feitas através de um token específico.
    
    Args:
        request: Requisição HTTP com token e ai_client_config
    
    Returns:
        JsonResponse: Status da operação com mensagem e código HTTP apropriado.
    """
    if request.method != 'POST':
        error = APPError(message='Método não permitido')
        response = APPResponse.create_failure(error)
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
            error = APPError(message='Token e configuração de IA são obrigatórios para ativação')
            response = APPResponse.create_failure(error)
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
                    error = APPError(message='Token não encontrado')
                    response = APPResponse.create_failure(error)
                    return JsonResponse(response.to_dict(), status=404)
                
                try:
                    ai_config = AIClientConfiguration.objects.get(id=ai_config_id, user=request.user)
                except AIClientConfiguration.DoesNotExist:
                    error = APPError(message='Configuração de IA não encontrada.')
                    response = APPResponse.create_failure(error)
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
            
            response = APPResponse.create_success(response_data)
            return JsonResponse(response.to_dict())
            
    except Exception as e:
        logger.exception(f"Erro ao alternar captura: {e}")
        error = APPError(message=str(e))
        response = APPResponse.create_failure(error)
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
            capture.file_data = AIExampleDict()
            capture.save()
                
            logger.info(f"Retornados {len(list(collection.items()))} exemplos para token {token.name}")
            response_data = {
                'examples': collection.to_dict(),
                'count': len(list(collection.items())),
            }
            response = APPResponse.create_success(response_data)
            return JsonResponse(response.to_dict())
            
        except TrainingCapture.DoesNotExist:
            response_data = {
                'examples': [], 
                'count': 0,
                'message': 'Não há captura configurada para este token.'
            }
            response = APPResponse.create_success(response_data)
            return JsonResponse(response.to_dict())
            
    except UserToken.DoesNotExist:
        error = APPError(message='Token não encontrado.')
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=404)
    except AIClientConfiguration.DoesNotExist:
        error = APPError(message='Configuração de IA não encontrada.')
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        logger.exception(f"Erro ao obter exemplos: {e}")
        error = APPError(message=str(e))
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=500)
=======
    """Ativa ou desativa a captura de exemplos de treinamento."""
    try:
        token_id = request.POST.get('token')
        ai_client_config_id = request.POST.get('ai_client_config')
        action = request.POST.get('action')       

        if action == 'activate':
            if not all([token_id, ai_client_config_id, action]):
                return JsonResponse({
                    'error': 'Parâmetros incompletos'
                }, status=400)
            
            token = get_object_or_404(UserToken, id=token_id, user=request.user)
            ai_client_config = get_object_or_404(AIClientConfiguration, id=ai_client_config_id, token=token)

            capture, created = TrainingCapture.objects.get_or_create(
                token=token,
                ai_client_config=ai_client_config,
                defaults={'is_active': True}
            )
            if not created:
                capture.is_active = True 
                capture.save()
            return JsonResponse({
                'message': 'Captura ativada com sucesso',
                'capture_id': capture.id
            })
        elif action == 'deactivate':
            TrainingCapture.objects.filter(
                token__user=request.user
            ).delete()
            
            return JsonResponse({
                'message': 'Captura desativada com sucesso'
            })
        else:
            return JsonResponse({
                'error': 'Ação inválida'
            }, status=400)

    except Exception as e:
        logger.exception("Erro ao alternar captura:")
        return JsonResponse({
            'error': f'Erro ao processar a requisição: {str(e)}'
        }, status=500)

@login_required
def capture_get_examples(request: HttpRequest, token_id: str, ai_id: int) -> JsonResponse:
    """Retorna os exemplos de treinamento capturados para uma IA."""
    token = get_object_or_404(UserToken, id=token_id, user=request.user)
    ai_config = get_object_or_404(AIClientConfiguration, 
        token=token, 
        id=ai_id,
        enabled=True
    )
    
    try:
        capture = TrainingCapture.objects.get(
            token=token, 
            ai_client_config=ai_config, 
            is_active=True
        )
        
        # Atualiza o último acesso
        capture.save()
        
        temp_file = capture.temp_file
        if not temp_file:
            return JsonResponse({'examples': []})
            
        with temp_file.open('r') as f:
            training_data = json.load(f)
            
        # Limpa o arquivo temporário após ler
        with temp_file.open('w') as f:
            json.dump([], f)
            
        return JsonResponse({'examples': training_data})
        
    except TrainingCapture.DoesNotExist:
        return JsonResponse({'error': 'Captura não está ativa.'}, status=400)
    except Exception as e:
        logger.exception("Erro ao carregar exemplos:")
        return JsonResponse({'error': 'Erro ao carregar exemplos.'}, status=500)
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
