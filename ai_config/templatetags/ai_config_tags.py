"""Módulo de filtros para templates relacionados à configuração de IA.

Este módulo contém filtros auxiliares em Django para manipulação de arquivos.
"""

from django import template
import os

register = template.Library()

@register.filter
def basename(value):
    """Retorna o nome base de um caminho de arquivo.

    Args:
        value (str): Caminho completo do arquivo.

    Returns:
        str: O nome do arquivo.
    """
    return os.path.basename(value)
