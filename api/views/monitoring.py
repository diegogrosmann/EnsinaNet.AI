"""Views para monitoramento e métricas da API.

Este módulo fornece endpoints para monitorar o uso da API,
métricas de desempenho e estatísticas de utilização.
"""

import json
import logging
from typing import Dict, Any
from django.http import JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import APILog
from accounts.models import UserToken

logger = logging.getLogger(__name__)

@login_required
def monitoring_dashboard(request: HttpRequest):
    """
    Retorna uma página HTML simples com um script de polling (a cada 30s)
    para atualizar uma tabela com os logs de requisições.

    Se o usuário não for staff, só vai conseguir visualizar os logs filtrados
    (essa lógica está em monitoring_data).
    """
    return render(request, 'monitoring/dashboard.html')


@login_required
def monitoring_data(request: HttpRequest):
    """
    Retorna JSON dos logs recentes.

    - Se user.is_staff: retorna todos os logs (APILog.objects.order_by('-timestamp')[:50]).
    - Caso contrário: retorna apenas os logs do próprio usuário (APILog.objects.filter(user=request.user)).
    """
    if request.user.is_staff:
        logs = APILog.objects.order_by('-timestamp')[:50]
    else:
        # Mostra apenas logs do próprio usuário
        logs = APILog.objects.filter(user=request.user).order_by('-timestamp')[:50]

    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'user_token': log.user_token.key if log.user_token else None,
            'path': log.path,
            'method': log.method,
            'status_code': log.status_code,
            'execution_time': log.execution_time,
            'timestamp': log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return JsonResponse({'logs': data}, safe=False)


@login_required
def api_usage_metrics(request) -> JsonResponse:
    """Retorna métricas de uso da API para o usuário atual.
    
    Calcula estatísticas como total de chamadas, tempo médio de resposta
    e distribuição de status code por token.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        JsonResponse: Métricas de uso da API.
    """
    try:
        # Período de análise (últimos 30 dias)
        start_date = timezone.now() - timedelta(days=30)
        
        # Obter logs do usuário
        user_logs = APILog.objects.filter(
            user=request.user,
            timestamp__gte=start_date
        ).select_related('user_token')
        
        # Calcular métricas por token
        token_metrics = {}
        for token in UserToken.objects.filter(user=request.user):
            token_logs = user_logs.filter(user_token=token)
            
            token_metrics[str(token.id)] = {
                'name': token.name,
                'total_calls': token_logs.count(),
                'avg_time': token_logs.aggregate(Avg('execution_time'))['execution_time__avg'] or 0,
                'status_codes': dict(token_logs.values_list('status_code').annotate(count=Count('id')))
            }
        
        logger.info(f"Métricas de uso geradas para usuário {request.user.email}")
        return JsonResponse({'metrics': token_metrics})
        
    except Exception as e:
        logger.error(f"Erro ao gerar métricas de uso: {str(e)}")
        return JsonResponse(
            {'error': 'Erro ao gerar métricas'}, 
            status=500
        )
