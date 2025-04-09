import logging

from core.types import (
    AIPrompt,
    APPResponse
)

from ai_config.models import TrainingCapture, AIClientConfiguration
from accounts.models import UserToken

logger = logging.getLogger(__name__)

def handle_training_capture(
    user_token: UserToken, 
    ai_config: AIClientConfiguration, 
    message: AIPrompt, 
    comparison_result: APPResponse
) -> None:
    try:
        try:
            capture = TrainingCapture.objects.get(
                token=user_token,
                ai_client_config=ai_config,
                is_active=True
            )
            
            if not comparison_result.error and comparison_result.response:
                from core.types.ai import AIExample
                example = AIExample(
                    system_message=message.system_message,
                    user_message=message.user_message,
                    response=comparison_result.response
                )
                
                capture.add_example(example)
                logger.info(f"Exemplo adicionado à captura de treinamento {capture.id}")
                
        except TrainingCapture.DoesNotExist:
            pass
            
    except Exception as e:
        logger.error(f"Erro durante captura de treinamento: {str(e)}", exc_info=True)
