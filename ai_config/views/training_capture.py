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

logger = logging.getLogger(__name__)

@login_required
@require_POST
def capture_toggle(request: HttpRequest) -> JsonResponse:
    """Ativa ou desativa a captura de exemplos de treinamento.
    
    Ativa/desativa a coleta automática de exemplos para treinamento de IA a partir
    das interações feitas através de um token específico.
    
    Args:
        request: Objeto de requisição HTTP.
    
    Returns:
        JsonResponse: Status da operação com mensagem e código HTTP apropriado.
    """
    try:
        token_id = request.POST.get('token')
        ai_client_config_id = request.POST.get('ai_client_config')
        action = request.POST.get('action')       
        logger.debug(f"Solicitação de {action} para captura - Token: {token_id}, AI: {ai_client_config_id}")

        if action == 'activate':
            if not all([token_id, ai_client_config_id, action]):
                logger.warning("Tentativa de ativar captura com parâmetros incompletos")
                return JsonResponse({
                    'error': 'Parâmetros incompletos'
                }, status=400)
            
            # Verificar se o token pertence ao usuário
            token = get_object_or_404(UserToken, id=token_id, user=request.user)
            # Verificar se a configuração da IA pertence ao usuário
            ai_client_config = get_object_or_404(AIClientConfiguration, user=request.user, id=ai_client_config_id)
            
            # Verificar se a IA está habilitada para este token
            try:
                token_ai_config = AIClientTokenConfig.objects.get(
                    token=token, 
                    ai_config=ai_client_config
                )
                
                if not token_ai_config.enabled:
                    logger.warning(f"Tentativa de ativar captura para IA não habilitada - Token: {token_id}, AI: {ai_client_config_id}")
                    return JsonResponse({
                        'error': 'A IA selecionada não está habilitada para este token. Por favor, habilite-a primeiro nas configurações do token.'
                    }, status=403)
                    
            except AIClientTokenConfig.DoesNotExist:
                logger.warning(f"Tentativa de ativar captura para combinação inválida - Token: {token_id}, AI: {ai_client_config_id}")
                return JsonResponse({
                    'error': 'A IA selecionada não está habilitada para este token. Por favor, habilite-a primeiro nas configurações do token.'
                }, status=403)

            # Desativar qualquer captura ativa existente
            with transaction.atomic():
                # Primeiro desativa qualquer captura existente
                TrainingCapture.objects.filter(token__user=request.user, is_active=True).update(is_active=False)
                
                # Agora cria ou ativa a nova captura
                capture, created = TrainingCapture.objects.get_or_create(
                    token=token,
                    ai_client_config=ai_client_config,
                    defaults={'is_active': True}
                )
                if not created:
                    capture.is_active = True 
                    capture.save()

            logger.info(f"Captura ativada para token '{token.name}' com IA '{ai_client_config.name}' pelo usuário {request.user.email}")
            return JsonResponse({
                'message': 'Captura ativada com sucesso',
                'capture_id': capture.id
            })
        elif action == 'deactivate':
            with transaction.atomic():
                captures = TrainingCapture.objects.filter(token__user=request.user, is_active=True)
                if captures.exists():
                    for capture in captures:
                        logger.info(f"Desativando captura para token '{capture.token.name}' do usuário {request.user.email}")
                    captures.delete()
                else:
                    logger.debug(f"Nenhuma captura ativa para desativar para o usuário {request.user.email}")
            
            return JsonResponse({
                'message': 'Captura desativada com sucesso'
            })
        else:
            logger.warning(f"Ação inválida solicitada: {action}")
            return JsonResponse({
                'error': 'Ação inválida'
            }, status=400)

    except UserToken.DoesNotExist:
        logger.warning(f"Token não encontrado na solicitação de captura: {token_id}")
        return JsonResponse({
            'error': 'Token não encontrado'
        }, status=404)
    except AIClientConfiguration.DoesNotExist:
        logger.warning(f"Configuração de IA não encontrada na solicitação de captura: {ai_client_config_id}")
        return JsonResponse({
            'error': 'Configuração de IA não encontrada'
        }, status=404)
    except Exception as e:
        logger.exception(f"Erro ao processar alternância de captura: {e}")
        return JsonResponse({
            'error': f'Erro ao processar a requisição: {str(e)}'
        }, status=500)

@login_required
def capture_get_examples(request: HttpRequest, token_id: str, ai_id: int) -> JsonResponse:
    """Retorna os exemplos de treinamento capturados para uma IA.
    
    Coleta exemplos do arquivo temporário da captura e limpa-o após leitura,
    permitindo que estes exemplos sejam carregados na interface do usuário.
    
    Args:
        request: Objeto de requisição HTTP.
        token_id: ID do token da captura.
        ai_id: ID da configuração de IA da captura.
    
    Returns:
        JsonResponse: Lista de exemplos capturados ou mensagem de erro.
    """
    try:
        # Verificar se o token pertence ao usuário
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        # Verificar se a configuração da IA pertence ao usuário
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        
        logger.debug(f"Buscando exemplos capturados para token '{token.name}' e IA '{ai_config.name}'")
        
        # Verificar se existe uma captura ativa para essa combinação
        try:
            capture = TrainingCapture.objects.get(
                token=token, 
                ai_client_config=ai_config, 
                is_active=True
            )
            
            # Atualiza o último acesso para renovar o timeout
            capture.save()
            
            temp_file = capture.temp_file
            if not temp_file:
                logger.debug(f"Nenhum arquivo temporário encontrado para captura: token '{token.name}', IA '{ai_config.name}'")
                return JsonResponse({'examples': []})
            
            # Carrega os exemplos capturados
            try:
                with temp_file.open('r') as f:
                    training_data = json.load(f)
                    example_count = len(training_data) if isinstance(training_data, list) else 0
                    logger.info(f"Lidos {example_count} exemplos da captura de {token.name} com {ai_config.name}")
            except json.JSONDecodeError:
                logger.warning(f"Arquivo de captura com formato JSON inválido: token '{token.name}', IA '{ai_config.name}'")
                training_data = []
                
            # Limpa o arquivo temporário após ler - zerando a lista de exemplos
            with temp_file.open('w') as f:
                json.dump([], f)
                logger.debug(f"Arquivo temporário de captura limpo após leitura: token '{token.name}', IA '{ai_config.name}'")
                
            return JsonResponse({'examples': training_data})
            
        except TrainingCapture.DoesNotExist:
            logger.warning(f"Tentativa de acessar exemplos sem captura ativa: token '{token.name}', IA '{ai_config.name}'")
            return JsonResponse({'error': 'Captura não está ativa.'}, status=400)
            
    except UserToken.DoesNotExist:
        logger.warning(f"Token não encontrado na solicitação de exemplos: {token_id}")
        return JsonResponse({'error': 'Token não encontrado.'}, status=404)
    except AIClientConfiguration.DoesNotExist:
        logger.warning(f"Configuração de IA não encontrada na solicitação de exemplos: {ai_id}")
        return JsonResponse({'error': 'Configuração de IA não encontrada.'}, status=404)
    except Exception as e:
        logger.exception(f"Erro ao carregar exemplos de captura para token {token_id}, IA {ai_id}: {e}")
        return JsonResponse({'error': 'Erro ao carregar exemplos de captura.'}, status=500)
