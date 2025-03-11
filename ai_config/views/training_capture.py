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
from ai_config.models import AIClientConfiguration, TrainingCapture, AIClientTokenConfig
from core.types import TrainingExampleData, TrainingCaptureData

logger = logging.getLogger(__name__)

@login_required
@require_POST
def capture_toggle(request: HttpRequest) -> JsonResponse:
    """Ativa ou desativa a captura de exemplos de treinamento.
    
    Ativa/desativa a coleta automática de exemplos para treinamento de IA a partir
    das interações feitas através de um token específico.
    
    Args:
        request: Requisição HTTP com token_id e ai_id
    
    Returns:
        JsonResponse: Status da operação com mensagem e código HTTP apropriado.
    """
    try:
        token_id = request.POST.get('token_id')
        ai_id = request.POST.get('ai_id')
        is_active = request.POST.get('is_active') == 'true'
        
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        
        with transaction.atomic():
            # Desativa qualquer captura ativa existente
            if is_active:
                TrainingCapture.objects.filter(token=token).update(is_active=False)
            
            # Obtém ou cria o objeto de captura
            capture, created = TrainingCapture.objects.get_or_create(
                token=token,
                ai_client_config=ai_config,
                defaults={'is_active': False}
            )
            
            capture.is_active = is_active
            capture.save()
            
            # Converte para tipo estruturado
            capture_data = TrainingCaptureData(
                id=capture.id,
                token_id=token.id,
                ai_client_config_id=ai_config.id,
                is_active=capture.is_active,
                temp_file=capture.temp_file.name if capture.temp_file else None,
                create_at=capture.create_at,
                last_activity=capture.last_activity
            )
            
            status = "ativada" if is_active else "desativada"
            logger.info(f"Captura {status} para token {token.name} com IA {ai_config.name}")
            
            return JsonResponse({
                'success': True,
                'active': is_active,
                'message': f"Captura {status} para {token.name}"
            })
    except UserToken.DoesNotExist:
        return JsonResponse({'error': 'Token não encontrado.'}, status=404)
    except AIClientConfiguration.DoesNotExist:
        return JsonResponse({'error': 'Configuração de IA não encontrada.'}, status=404)
    except Exception as e:
        logger.exception(f"Erro ao alternar captura: {e}")
        return JsonResponse({'error': str(e)}, status=500)

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
            
            # Lê o arquivo temporário
            if capture.temp_file and capture.temp_file.storage.exists(capture.temp_file.name):
                with open(capture.temp_file.path, 'r') as file:
                    examples_json = json.load(file)
                
                # Converte para tipo estruturado
                examples = [
                    TrainingExampleData(
                        system_message=example.get('system_message', ''),
                        user_message=example['user_message'],
                        response=example['response']
                    )
                    for example in examples_json
                ]
                
                # Limpa o arquivo após leitura
                with open(capture.temp_file.path, 'w') as file:
                    json.dump([], file)
                
                # Converte para formato de resposta JSON
                examples_data = [
                    {
                        'system_message': ex.system_message,
                        'user_message': ex.user_message,
                        'response': ex.response
                    }
                    for ex in examples
                ]
                
                logger.info(f"Retornados {len(examples)} exemplos para token {token.name}")
                return JsonResponse({
                    'success': True,
                    'examples': examples_data,
                    'count': len(examples)
                })
            else:
                return JsonResponse({
                    'success': True, 
                    'examples': [], 
                    'count': 0,
                    'message': 'Nenhum exemplo capturado ainda.'
                })
        except TrainingCapture.DoesNotExist:
            return JsonResponse({
                'success': True, 
                'examples': [], 
                'count': 0,
                'message': 'Não há captura configurada para este token.'
            })
            
    except UserToken.DoesNotExist:
        return JsonResponse({'error': 'Token não encontrado.'}, status=404)
    except AIClientConfiguration.DoesNotExist:
        return JsonResponse({'error': 'Configuração de IA não encontrada.'}, status=404)
    except Exception as e:
        logger.exception(f"Erro ao obter exemplos: {e}")
        return JsonResponse({'error': str(e)}, status=500)
