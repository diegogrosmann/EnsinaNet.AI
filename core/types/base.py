"""
Tipos básicos e genéricos para uso em toda a aplicação.
"""
from typing import Dict, Any, TypeVar

# -----------------------------------------------------------------------------
# Tipos básicos
# -----------------------------------------------------------------------------

JSONDict = Dict[str, Any]
"""
Representa um dicionário JSON genérico onde as chaves são strings e os valores
podem ser de qualquer tipo. Utilizado para APIs, serialização e deserialização
de dados em formato JSON.
"""

# -----------------------------------------------------------------------------
# Tipos genéricos
# -----------------------------------------------------------------------------

T = TypeVar('T')
"""
Variável de tipo genérica para uso em funções e classes parametrizadas.
Permite a criação de componentes reutilizáveis que preservam informações 
de tipo durante operações genéricas.
"""
