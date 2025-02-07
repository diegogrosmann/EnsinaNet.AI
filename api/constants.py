from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AIClientConfig:
    """Configuração para clientes de IA.

    Args:
        api_key (str): Chave de API.
        model_name (str): Nome do modelo.
        base_instruction (str, optional): Instrução base.
        prompt (str, optional): Prompt inicial.
        responses (str, optional): Respostas padrão.
        configurations (Dict, optional): Configurações adicionais.
        created_at (datetime, optional): Data de criação.
        enabled (bool, optional): Indica se está habilitado.
        api_url (str, optional): URL da API.
        use_system_message (bool, optional): Indica se utiliza "system message".
    """
    api_key: str
    model_name: str
    base_instruction: str = ""
    prompt: str = ""
    responses: str = ""
    configurations: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True,
    api_url: str = None
    use_system_message: bool = False

@dataclass
class ProcessingResult:
    """Resultado do processamento realizado pelas funções da API.

    Args:
        success (bool): Indica se o processamento foi bem sucedido.
        message (str): Mensagem associada ao resultado.
        data (Optional[Dict], optional): Dados retornados.
        error (Optional[str], optional): Descrição do erro, se houver.
    """
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None

