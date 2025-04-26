<<<<<<< HEAD
"""Views públicas da aplicação.

Este módulo contém as views que não requerem autenticação,
como a página inicial e recursos públicos.
"""

import logging
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

def index(request: HttpRequest) -> HttpResponse:
    """Renderiza a página inicial pública.
    
    Se o usuário estiver autenticado, redireciona para
    a página de gerenciamento de tokens.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        HttpResponse: Página renderizada ou redirecionamento.
    """
    if request.user.is_authenticated:
        logger.debug(f"Usuário autenticado redirecionado: {request.user.email}")
        return redirect('accounts:tokens_manage')
        
    logger.debug("Renderizando página inicial para usuário anônimo")
=======
from django.shortcuts import render, redirect

def index(request):
    if request.user.is_authenticated:
        return redirect('accounts:tokens_manage') 
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
    return render(request, 'public/index.html')
