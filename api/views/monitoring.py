"""Views para monitoramento e métricas da API.

Este módulo fornece endpoints para monitorar o uso da API,
métricas de desempenho e estatísticas de utilização.
"""

import logging
from typing import List, Dict
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import APILog
from accounts.models import UserToken
from core.types import APILog, TokenMetrics, UsageMetrics

logger = logging.getLogger(__name__)

@login_required
def monitoring_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Retorna uma página HTML com um script de polling para logs de requisições.

    Se o usuário não for staff, só vai conseguir visualizar os logs filtrados
    (essa lógica está em monitoring_data).
    
    Args:
        request: Objeto de requisição HTTP
        
    Returns:
        HttpResponse: Página do dashboard de monitoramento
    """
    return render(request, 'monitoring/dashboard.html')


@login_required
def monitoring_data(request: HttpRequest) -> JsonResponse:
    """
    Retorna JSON dos logs recentes da API.

    Args:
        request: Objeto de requisição HTTP
        
    Returns:
        JsonResponse: Dados de monitoramento filtrados por permissão do usuário
    """
    if request.user.is_staff:
        logs = APILog.objects.order_by('-timestamp')[:50]
    else:
        # Mostra apenas logs do próprio usuário
        logs = APILog.objects.filter(user=request.user).order_by('-timestamp')[:50]

    # Converte logs para o formato estruturado
    log_data_list: List[APILog] = []
    for log in logs:
        log_data_list.append(log.to_log_data())
    
    # Converte para formato compatível com JSON
    data = []
    for log in log_data_list:
        data.append({
            'id': log.id,
            'user_token': log.user_token,
            'path': log.path,
            'method': log.method,
            'status_code': log.status_code,
            'execution_time': log.execution_time,
            'timestamp': log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return JsonResponse({'logs': data}, safe=False)


@login_required
def api_usage_metrics(request: HttpRequest) -> JsonResponse:
    """Retorna métricas de uso da API para o usuário atual.
    
    Calcula estatísticas como total de chamadas, tempo médio de resposta
    e distribuição de status code por token.
    
    Args:
        request: Objeto de requisição HTTP
        
    Returns:
        JsonResponse: Métricas de uso da API
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
        token_metrics: TokenMetrics = {}
        for token in UserToken.objects.filter(user=request.user):
            token_logs = user_logs.filter(user_token=token)
            status_codes = dict(token_logs.values_list('status_code').annotate(count=Count('id')))
            
            metrics: UsageMetrics = {
                'name': token.name,
                'total_calls': token_logs.count(),
                'avg_time': token_logs.aggregate(Avg('execution_time'))['execution_time__avg'] or 0,
                'status_codes': status_codes
            }
            token_metrics[str(token.id)] = metrics
        
        logger.info(f"Métricas de uso geradas para usuário {request.user.email}")
        return JsonResponse({'metrics': token_metrics})
        
    except Exception as e:
        logger.error(f"Erro ao gerar métricas de uso: {str(e)}")
        return JsonResponse(
            {'error': 'Erro ao gerar métricas'}, 
            status=500
        )
