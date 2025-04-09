"""Views para monitoramento e métricas da API.

Este módulo fornece endpoints para monitorar o uso da API,
incluindo métricas de desempenho, estatísticas de utilização
e logs detalhados de requisições.
"""

import logging
import json
import dataclasses
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from django.utils.dateparse import parse_date

from core.types.errors import APPError

from ..models import APILog
from accounts.models import UserToken
from core.types import APPResponse

logger = logging.getLogger(__name__)

@login_required
def monitoring_dashboard(request: HttpRequest) -> HttpResponse:
    """Renderiza o dashboard principal de monitoramento.
    
    Retorna uma página HTML com um script de polling para logs de requisições.
    Se o usuário não for staff, só vai conseguir visualizar os logs filtrados
    relacionados a seu próprio usuário.
    
    Args:
        request: Requisição HTTP.
        
    Returns:
        HttpResponse: Página renderizada do dashboard de monitoramento.
        
    Raises:
        Exception: Erros são tratados pelo Django e renderizam página de erro
    """
    logger.info(f"Acessando dashboard de monitoramento: usuário {request.user.username}")
    
    try:
        # Verificar se usuário é staff para determinar o modo de exibição
        is_staff = request.user.is_staff
        
        # Obter tokens do usuário ou todos os tokens (para staff)
        tokens = UserToken.objects.all()
        if not is_staff:
            tokens = tokens.filter(user=request.user)
            
        tokens = tokens.values('id', 'name', 'user__username')
        
        # Preparar contexto para o template
        context = {
            'is_staff': is_staff,
            'tokens': tokens,
            'user': request.user,
        }
        
        return render(request, 'monitoring/dashboard.html', context)
    except Exception as e:
        logger.exception(f"Erro ao renderizar dashboard: {str(e)}")
        # Redirecionar para uma página de erro ou renderizar template de erro
        return render(request, 'monitoring/error.html', {
            'error_message': "Erro ao carregar dashboard de monitoramento"
        })

@login_required
def monitoring_data(request: HttpRequest) -> JsonResponse:
    """Retorna dados de logs recentes da API em formato JSON.
    
    Filtra os logs conforme permissões do usuário:
    - Usuários staff podem ver todos os logs
    - Usuários normais veem apenas seus próprios logs
    
    Args:
        request: Requisição HTTP.
        
    Returns:
        JsonResponse: Logs recentes da API formatados como JSON.
        
    Raises:
        APIError: Se houver erro ao processar logs
    """
    try:
        # Verificar permissões do usuário
        is_staff = request.user.is_staff
        
        # Construir a query base
        logs_query = APILog.objects.order_by('-timestamp')
        
        # Se não for staff, filtrar apenas logs do próprio usuário
        if not is_staff:
            user_tokens = UserToken.objects.filter(user=request.user).values_list('id', flat=True)
            logs_query = logs_query.filter(user_token__in=user_tokens)
        
        # Aplicar filtros adicionais
        token_id = request.GET.get('token_id')
        if token_id:
            logs_query = logs_query.filter(user_token_id=token_id)
            
        status_code = request.GET.get('status_code')
        if status_code:
            logs_query = logs_query.filter(status_code=status_code)
            
        # Paginação
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 25))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Obter logs paginados
        logs = logs_query[start_idx:end_idx]
        total_logs = logs_query.count()
        
        # Converter para formato de resposta
        logs_data = []
        for log in logs:
            log_data = {
                'id': log.id,
                'path': log.path,
                'method': log.method,
                'status_code': log.status_code,
                'execution_time': log.execution_time,
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.username if log.user else None,
                'token': {
                    'id': log.user_token.id,
                    'name': log.user_token.name
                } if log.user_token else None
            }
            logs_data.append(log_data)
        
        # Construir resposta tipada
        response = APPResponse.create_success({
            'logs': logs_data,
            'total': total_logs,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_logs + per_page - 1) // per_page
        })
        
        return JsonResponse(response.to_dict(), status=200)
    except Exception as e:
        logger.exception(f"Erro ao obter dados de monitoramento: {str(e)}")
        error = APPError(message=f"Erro ao obter logs: {str(e)}")
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)

@login_required
def monitoring_stats(request: HttpRequest) -> JsonResponse:
    """Retorna estatísticas gerais de uso da API.
    
    Obtém métricas e estatísticas agregadas com base nos logs
    da API, podendo filtrar por token e período.
    
    Args:
        request: Requisição HTTP.
        
    Returns:
        JsonResponse: Estatísticas e métricas de uso formatadas como JSON.
        
    Raises:
        APIError: Se houver erro ao processar estatísticas
    """
    try:
        # Verificar permissões do usuário
        is_staff = request.user.is_staff
        
        # Parâmetros de filtro
        token_id = request.GET.get('token_id')
        
        # Filtragem por data
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        days = int(request.GET.get('days', 7))
        
        # Se as datas específicas foram fornecidas, usá-las; caso contrário, usar days
        if start_date_str:
            start_date = parse_date(start_date_str)
            if not start_date:
                start_date = timezone.now() - timedelta(days=days)
        else:
            start_date = timezone.now() - timedelta(days=days)
            
        # Adicionar a hora ao campo de data
        start_datetime = datetime.combine(start_date, datetime.min.time())
        start_datetime = timezone.make_aware(start_datetime)
            
        # Construir a query base com filtro de data inicial
        logs_query = APILog.objects.filter(timestamp__gte=start_datetime)
        
        # Se uma data final foi fornecida, aplicar o filtro
        if end_date_str:
            end_date = parse_date(end_date_str)
            if end_date:
                # Adicionar um dia inteiro para incluir todo o dia final
                end_datetime = datetime.combine(end_date, datetime.max.time())
                end_datetime = timezone.make_aware(end_datetime)
                logs_query = logs_query.filter(timestamp__lte=end_datetime)
        
        # Se não for staff, filtrar apenas logs do próprio usuário
        if not is_staff:
            user_tokens = UserToken.objects.filter(user=request.user).values_list('id', flat=True)
            logs_query = logs_query.filter(user_token__in=user_tokens)
        
        # Aplicar filtro de token se fornecido
        if token_id:
            logs_query = logs_query.filter(user_token_id=token_id)
        
        # Estatísticas agregadas
        total_calls = logs_query.count()
        avg_time = logs_query.aggregate(Avg('execution_time'))['execution_time__avg'] or 0
        
        # Distribuição por status code
        status_distribution = logs_query.values('status_code').annotate(
            count=Count('id')
        ).order_by('status_code')
        
        # Distribuição por método HTTP
        method_distribution = logs_query.values('method').annotate(
            count=Count('id')
        ).order_by('method')
        
        # Distribuição diária de chamadas (últimos N dias)
        daily_calls = logs_query.extra(
            select={'day': 'DATE(timestamp)'}
        ).values('day').annotate(count=Count('id')).order_by('day')
        
        # Obter tokens disponíveis para o usuário
        tokens_query = UserToken.objects.all()
        if not is_staff:
            tokens_query = tokens_query.filter(user=request.user)
            
        tokens = [{'id': token.id, 'name': token.name} for token in tokens_query]
        
        # Construir resposta tipada
        stats_data = {
            'total_calls': total_calls,
            'avg_time': avg_time,
            'status_distribution': list(status_distribution),
            'method_distribution': list(method_distribution),
            'daily_calls': list(daily_calls),
            'period_days': days,
            'tokens': tokens
        }
        
        response = APPResponse.create_success(stats_data)
        return JsonResponse(response.to_dict(), status=200)
        
    except Exception as e:
        logger.exception(f"Erro ao gerar estatísticas: {str(e)}")
        error = APPError(message=f"Erro ao processar estatísticas: {str(e)}")
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)

@login_required
def monitoring_requests(request: HttpRequest) -> JsonResponse:
    """Retorna lista paginada de requisições à API.
    
    Fornece dados detalhados sobre as requisições à API com suporte
    a paginação e filtros por data e token.
    
    Args:
        request: Requisição HTTP.
        
    Returns:
        JsonResponse: Lista paginada de requisições.
        
    Raises:
        APIError: Se houver erro ao processar requisições
    """
    try:
        # Verificar permissões do usuário
        is_staff = request.user.is_staff
        
        # Construir a query base
        logs_query = APILog.objects.order_by('-timestamp')
        
        # Se não for staff, filtrar apenas logs do próprio usuário
        if not is_staff:
            user_tokens = UserToken.objects.filter(user=request.user).values_list('id', flat=True)
            logs_query = logs_query.filter(user_token__in=user_tokens)
        
        # Aplicar filtros
        token_id = request.GET.get('token_id')
        if token_id:
            logs_query = logs_query.filter(user_token_id=token_id)
            
        status_code = request.GET.get('status_code')
        if status_code:
            logs_query = logs_query.filter(status_code=status_code)
            
        method = request.GET.get('method')
        if method:
            logs_query = logs_query.filter(method=method)
            
        path = request.GET.get('path')
        if path:
            logs_query = logs_query.filter(path__icontains=path)
            
        # Filtragem por data
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        days = int(request.GET.get('days', 7))
        
        # Se as datas específicas foram fornecidas, usá-las; caso contrário, usar days
        if start_date_str:
            start_date = parse_date(start_date_str)
            if not start_date:
                start_date = timezone.now() - timedelta(days=days)
        else:
            start_date = timezone.now() - timedelta(days=days)
            
        # Adicionar a hora ao campo de data
        start_datetime = datetime.combine(start_date, datetime.min.time())
        start_datetime = timezone.make_aware(start_datetime)
            
        # Aplicar filtro de data inicial
        logs_query = logs_query.filter(timestamp__gte=start_datetime)
        
        # Se uma data final foi fornecida, aplicar o filtro
        if end_date_str:
            end_date = parse_date(end_date_str)
            if end_date:
                # Adicionar um dia inteiro para incluir todo o dia final
                end_datetime = datetime.combine(end_date, datetime.max.time())
                end_datetime = timezone.make_aware(end_datetime)
                logs_query = logs_query.filter(timestamp__lte=end_datetime)
        
        # Paginação
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 25))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Obter logs paginados
        logs = logs_query[start_idx:end_idx]
        total_logs = logs_query.count()
        
        # Converter para formato de resposta
        logs_data = []
        for log in logs:
            log_data = {
                'id': log.id,
                'path': log.path,
                'method': log.method,
                'status_code': log.status_code,
                'execution_time': log.execution_time,
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.username if log.user else None,
                'token': {
                    'id': log.user_token.id if log.user_token else None,
                    'name': log.user_token.name if log.user_token else None
                }
            }
            logs_data.append(log_data)
        
        # Construir resposta tipada
        response_data = {
            'requests': logs_data,
            'total': total_logs,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_logs + per_page - 1) // per_page,
            'filter': {
                'token_id': token_id,
                'status_code': status_code,
                'method': method,
                'path': path,
                'days': days,
                'start_date': start_date_str,
                'end_date': end_date_str
            }
        }
        
        response = APPResponse.create_success(response_data)
        return JsonResponse(response.to_dict(), status=200)
        
    except Exception as e:
        logger.exception(f"Erro ao listar requisições: {str(e)}")
        error = APPError(message=f"Erro ao processar requisições: {str(e)}")
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)

@login_required
def monitoring_request_details(request: HttpRequest, request_id: int) -> JsonResponse:
    """Retorna detalhes de uma requisição específica.
    
    Fornece todos os dados disponíveis sobre uma requisição específica,
    incluindo corpo da requisição e resposta.
    
    Args:
        request: Requisição HTTP.
        request_id: ID da requisição a ser detalhada.
        
    Returns:
        JsonResponse: Detalhes da requisição.
        
    Raises:
        APIError: Se houver erro ao processar detalhes
    """
    try:
        # Obter o log da requisição
        log = get_object_or_404(APILog, id=request_id)
        
        # Verificar permissões do usuário
        is_staff = request.user.is_staff
        if not is_staff and log.user_token and log.user_token.user != request.user:
            # Usuário não tem permissão para acessar este log
            error = APPError(message="Sem permissão para acessar este log")
            response = APPResponse.create_failure(error)
            return JsonResponse(response.to_dict(), status=403)
        
        # Formatar o request_body e response_body como JSON se possível
        request_body = None
        response_body = None
        
        if log.request_body:
            try:
                request_body = json.loads(log.request_body)
            except json.JSONDecodeError:
                request_body = log.request_body
        
        if log.response_body:
            try:
                response_body = json.loads(log.response_body)
            except json.JSONDecodeError:
                response_body = log.response_body
        
        # Construir resposta tipada
        log_details = {
            'id': log.id,
            'path': log.path,
            'method': log.method,
            'status_code': log.status_code,
            'execution_time': log.execution_time,
            'timestamp': log.timestamp.isoformat(),
            'user': log.user.username if log.user else None,
            'token': {
                'id': log.user_token.id,
                'name': log.user_token.name
            } if log.user_token else None,
            'requester_ip': log.requester_ip,
            'request_body': request_body,
            'response_body': response_body
        }
        
        response = APPResponse.create_success(log_details)
        return JsonResponse(response.to_dict(), status=200)
        
    except Exception as e:
        logger.exception(f"Erro ao obter detalhes da requisição {request_id}: {str(e)}")
        error = APPError(message=f"Erro ao processar detalhes: {str(e)}")
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)
