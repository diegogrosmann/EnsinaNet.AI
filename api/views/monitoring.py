"""
Módulo que contém as views para o painel de monitoramento da API.

Classes/Views:
    monitoring_dashboard(request): Retorna a página HTML de monitoramento.
    monitoring_data(request): Retorna JSON com dados de logs.
"""

import json
from datetime import datetime, timedelta

from django.shortcuts import render
from django.http import JsonResponse, HttpRequest
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required

from api.models import APILog

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
