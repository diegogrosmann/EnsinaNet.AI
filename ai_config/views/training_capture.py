import logging
import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from accounts.models import UserToken
from ai_config.models import AIClientConfiguration, TrainingCapture, AIClientTokenConfig

logger = logging.getLogger(__name__)

@login_required
@require_POST
def capture_toggle(request: HttpRequest) -> JsonResponse:
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
            ai_client_config = get_object_or_404(AIClientConfiguration, user=request.user, id=ai_client_config_id)
            
            # Verificar se a IA está habilitada para este token
            try:
                token_ai_config = AIClientTokenConfig.objects.get(
                    token=token, 
                    ai_config=ai_client_config
                )
                
                if not token_ai_config.enabled:
                    return JsonResponse({
                        'error': 'A IA selecionada não está habilitada para este token. Por favor, habilite-a primeiro nas configurações do token.'
                    }, status=403)
                    
            except AIClientTokenConfig.DoesNotExist:
                return JsonResponse({
                    'error': 'A IA selecionada não está habilitada para este token. Por favor, habilite-a primeiro nas configurações do token.'
                }, status=403)

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
        id=ai_id,
        user=request.user
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
        
        try:
            with temp_file.open('r') as f:
                training_data = json.load(f)
        except json.JSONDecodeError:
            training_data = []
            
        # Limpa o arquivo temporário após ler
        with temp_file.open('w') as f:
            json.dump([], f)
            
        return JsonResponse({'examples': training_data})
        
    except TrainingCapture.DoesNotExist:
        return JsonResponse({'error': 'Captura não está ativa.'}, status=400)
    except Exception as e:
        logger.exception("Erro ao carregar exemplos:")
        return JsonResponse({'error': 'Erro ao carregar exemplos.'}, status=500)
