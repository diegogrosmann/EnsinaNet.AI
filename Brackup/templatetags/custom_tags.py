from django import template
import os

register = template.Library()

@register.filter
def basename(value):
    """Retorna o nome base do arquivo a partir do caminho informado.
    
    Argumentos:
        value (str): Caminho completo do arquivo.
    
    Retorna:
        str: Nome base do arquivo.
    """
    return os.path.basename(value)
