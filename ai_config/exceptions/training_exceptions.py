from ai_config.exceptions import BaseAIConfigException


class TrainingException(BaseAIConfigException):
    """Exceção para erros no processo de treinamento."""
    
    def __init__(self, message=None, model_id=None, phase=None, metrics=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if model_id:
            additional_data['model_id'] = model_id
        if phase:
            additional_data['phase'] = phase
        if metrics:
            additional_data['metrics'] = metrics
            
        super().__init__(message=message, additional_data=additional_data, **kwargs)
