"""Views para monitoramento e métricas da API.

Este módulo fornece endpoints para monitorar o uso da API,
métricas de desempenho e estatísticas de utilização.
"""

import logging
import json
from typing import List, Dict, Optional, Any
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import APILog
from accounts.models import UserToken
from core.types.api_response import APPResponse
from core.types.monitoring import TokenMetrics, UsageMetrics

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
    try:
        if request.user.is_staff:
            logs = APILog.objects.order_by('-timestamp')[:50]
        else:
            # Mostra apenas logs do próprio usuário
            logs = APILog.objects.filter(user=request.user).order_by('-timestamp')[:50]

        # Converte logs para o formato estruturado
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
        
        response = APPResponse(success=True, data={'logs': data})
        return JsonResponse(response.to_dict())
    except Exception as e:
        logger.error(f"Erro ao buscar dados de monitoramento: {str(e)}")
        response = APPResponse(success=False, error=f"Erro ao buscar dados: {str(e)}")
        return JsonResponse(response.to_dict())


@login_required
def monitoring_stats(request: HttpRequest) -> JsonResponse:
    """
    Retorna estatísticas gerais de uso da API.
    
    Args:
        request: Objeto de requisição HTTP
        
    Returns:
        JsonResponse: Estatísticas de uso da API em formato APPResponse
    """
    try:
        # Obter parâmetros de filtro
        token_id = request.GET.get('token')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        # Aplicar filtros
        query_filters = Q()
        
        # Filtrar por usuário, a menos que seja staff
        if not request.user.is_staff:
            query_filters &= Q(user=request.user)
        
        # Filtrar por token se especificado
        if token_id:
            query_filters &= Q(user_token_id=token_id)
        
        # Preparar filtros de data
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                query_filters &= Q(timestamp__gte=start_date)
            except ValueError:
                pass
        
        if end_date_str:
            try:
                # Adicionar um dia para incluir todo o dia final
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query_filters &= Q(timestamp__lte=end_date)
            except ValueError:
                pass
        
        # Período padrão: últimos 30 dias
        if not start_date_str and not end_date_str:
            default_start = timezone.now() - timedelta(days=30)
            query_filters &= Q(timestamp__gte=default_start)
        
        # Obter logs com os filtros aplicados
        logs = APILog.objects.filter(query_filters)
        
        # Calcular estatísticas
        total_requests = logs.count()
        success_count = logs.filter(status_code__lt=400).count()
        error_count = total_requests - success_count
        avg_time = logs.aggregate(avg_time=Avg('execution_time'))['avg_time'] or 0
        
        # Formatar tempo médio para milissegundos
        avg_time_ms = round(avg_time * 1000)
        
        # Preparar dados por hora (últimas 24h)
        last_24h = timezone.now() - timedelta(hours=24)
        hourly_logs = logs.filter(timestamp__gte=last_24h)
        
        # Agrupar por hora
        hour_counts = {}
        for log in hourly_logs:
            hour_key = log.timestamp.strftime('%Y-%m-%d %H:00')
            hour_counts[hour_key] = hour_counts.get(hour_key, 0) + 1
        
        # Preparar dados para o gráfico
        sorted_hours = sorted(hour_counts.keys())
        requests_by_hour = {
            'labels': sorted_hours,
            'values': [hour_counts[hour] for hour in sorted_hours]
        }
        
        # Obter tokens disponíveis para filtro
        available_tokens = []
        token_queryset = UserToken.objects.all()
        
        # Se não for staff, limitar aos tokens do próprio usuário
        if not request.user.is_staff:
            token_queryset = token_queryset.filter(user=request.user)
        
        for token in token_queryset:
            available_tokens.append({
                'id': token.id,
                'name': token.name or token.key[:8]  # Nome ou prefixo do token
            })
        
        # Preparar resposta
        data = {
            'total_requests': total_requests,
            'success_count': success_count,
            'error_count': error_count,
            'avg_time': avg_time_ms,
            'requests_by_hour': requests_by_hour,
            'tokens': available_tokens
        }
        
        response = APPResponse(success=True, data=data)
        return JsonResponse(response.to_dict())
        
    except Exception as e:
        logger.error(f"Erro ao gerar estatísticas: {str(e)}")
        response = APPResponse(success=False, error=f"Erro ao gerar estatísticas: {str(e)}")
        return JsonResponse(response.to_dict())


@login_required
def monitoring_requests(request: HttpRequest) -> JsonResponse:
    """
    Retorna lista paginada de requisições à API.
    
    Args:
        request: Objeto de requisição HTTP
        
    Returns:
        JsonResponse: Lista paginada de requisições em formato APPResponse
    """
    try:
        # Obter parâmetros de paginação e filtro
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        token_id = request.GET.get('token')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        # Validar página
        if page < 1:
            page = 1
        
        # Aplicar filtros
        query_filters = Q()
        
        # Filtrar por usuário, a menos que seja staff
        if not request.user.is_staff:
            query_filters &= Q(user=request.user)
        
        # Filtrar por token se especificado
        if token_id:
            query_filters &= Q(user_token_id=token_id)
        
        # Preparar filtros de data
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                query_filters &= Q(timestamp__gte=start_date)
            except ValueError:
                pass
        
        if end_date_str:
            try:
                # Adicionar um dia para incluir todo o dia final
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query_filters &= Q(timestamp__lte=end_date)
            except ValueError:
                pass
        
        # Obter logs com os filtros aplicados
        logs = APILog.objects.filter(query_filters).order_by('-timestamp')
        
        # Calcular paginação
        total_items = logs.count()
        total_pages = (total_items + page_size - 1) // page_size  # Arredondar para cima
        
        # Ajustar página se estiver fora dos limites
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        # Calcular offsets
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Obter registros da página atual
        page_logs = logs[start_idx:end_idx]
        
        # Formatar dados para a resposta
        requests_data = []
        for log in page_logs:
            token_name = log.user_token.name if log.user_token else "N/A"
            if not token_name and log.user_token:
                token_name = f"Token {log.user_token.key[:8]}..."
            
            requests_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'token_name': token_name,
                'endpoint': f"{log.method} {log.path}",
                'status_code': log.status_code,
                'response_time': round(log.execution_time * 1000)  # Converter para ms
            })
        
        # Preparar informações de paginação
        pagination_info = {
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'total': total_items,
            'from': start_idx + 1 if total_items > 0 else 0,
            'to': min(end_idx, total_items) if total_items > 0 else 0
        }
        
        # Preparar resposta
        data = {
            'requests': requests_data,
            'pagination': pagination_info
        }
        
        response = APPResponse(success=True, data=data)
        return JsonResponse(response.to_dict())
        
    except Exception as e:
        logger.error(f"Erro ao listar requisições: {str(e)}")
        response = APPResponse(success=False, error=f"Erro ao listar requisições: {str(e)}")
        return JsonResponse(response.to_dict())


@login_required
def monitoring_request_details(request: HttpRequest, request_id: int) -> JsonResponse:
    """
    Retorna detalhes de uma requisição específica.
    
    Args:
        request: Objeto de requisição HTTP
        request_id: ID da requisição a ser detalhada
        
    Returns:
        JsonResponse: Detalhes da requisição em formato APPResponse
    """
    try:
        # Preparar query base
        query = Q(id=request_id)
        
        # Se não for staff, restringir aos logs do próprio usuário
        if not request.user.is_staff:
            query &= Q(user=request.user)
        
        # Buscar o log
        log = get_object_or_404(APILog, query)
        
        # Formatar token
        token_name = log.user_token.name if log.user_token else "N/A"
        if not token_name and log.user_token:
            token_name = f"Token {log.user_token.key[:8]}..."
        
        # Tentar parsear os corpos como JSON
        try:
            request_body = json.loads(log.request_body) if log.request_body else {}
        except (json.JSONDecodeError, TypeError):
            request_body = log.request_body
        
        try:
            response_body = json.loads(log.response_body) if log.response_body else {}
        except (json.JSONDecodeError, TypeError):
            response_body = log.response_body
        
        # Parsear headers (eles podem estar em formato string ou JSON)
        headers = {}
        # Headers seriam armazenados em um campo adicional, se existente
        # Este é um exemplo, você pode precisar ajustar conforme seu modelo
        
        # Preparar dados detalhados
        log_details = {
            'id': log.id,
            'timestamp': log.timestamp.isoformat(),
            'token_name': token_name,
            'endpoint': f"{log.method} {log.path}",
            'status_code': log.status_code,
            'response_time': round(log.execution_time * 1000),  # Converter para ms
            'request_body': request_body,
            'response_body': response_body,
            'headers': headers
        }
        
        response = APPResponse(success=True, data=log_details)
        return JsonResponse(response.to_dict())
        
    except Exception as e:
        logger.error(f"Erro ao buscar detalhes da requisição {request_id}: {str(e)}")
        response = APPResponse(success=False, error=f"Erro ao buscar detalhes da requisição: {str(e)}")
        return JsonResponse(response.to_dict())


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
        token_metrics: Dict[str, Dict[str, Any]] = {}
        for token in UserToken.objects.filter(user=request.user):
            token_logs = user_logs.filter(user_token=token)
            status_codes = dict(token_logs.values_list('status_code').annotate(count=Count('id')))
            
            metrics: Dict[str, Any] = {
                'name': token.name,
                'total_calls': token_logs.count(),
                'avg_time': token_logs.aggregate(Avg('execution_time'))['execution_time__avg'] or 0,
                'status_codes': status_codes
            }
            token_metrics[str(token.id)] = metrics
        
        logger.info(f"Métricas de uso geradas para usuário {request.user.email}")
        response = APPResponse(success=True, data={'metrics': token_metrics})
        return JsonResponse(response.to_dict())
        
    except Exception as e:
        logger.error(f"Erro ao gerar métricas de uso: {str(e)}")
        response = APPResponse(success=False, error=f"Erro ao gerar métricas de uso: {str(e)}")
        return JsonResponse(response.to_dict(), status=500)
