"""View para verificar o status de operações de comparação assíncronas e listar operações."""

import logging

from django.http import JsonResponse
from django.http import HttpRequest, HttpResponse

from rest_framework.decorators import api_view
from rest_framework import status

from core.types.app_response import APPResponse
from core.models import Operation

from accounts.models import UserToken

logger = logging.getLogger(__name__)

@api_view(['GET'])
def operation_status(request: HttpRequest, operation_id: str) -> HttpResponse:
    """
    Verifica o status de uma operação de comparação assíncrona.
    
    - Recebe o operation_id pela URL;
    - Busca a operação no banco e converte para OperationData;
    - Retorna o get_summary() da OperationData.
    """
    try:
        # Extrai e valida token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
        
        # Busca o token do usuário
        user_token = UserToken.objects.get(key=token_key)
        
        # Busca a operação no banco de dados
        try:
            operation_data = Operation.objects.get(
                operation_id=operation_id,
                user_token=user_token
            ).to_operation_data()
        except Operation.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f"Operação não encontrada: {operation_id}"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Monta o resumo consolidado
        summary = operation_data.get_summary()
        response = APPResponse.create_success(summary)
        return JsonResponse(response.to_dict(), status=status.HTTP_200_OK)
        
    except UserToken.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido'
        }, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception(f"Erro ao verificar status de operação {operation_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f"Erro ao verificar status da operação: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def operations_list(request: HttpRequest) -> HttpResponse:
    """
    Lista todas as operações de longa duração de um usuário.
    
    - Pode filtrar por tipo de operação e status;
    - Retorna várias operações via get_summary().
    """
    try:
        # Extrai e valida token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
        
        # Busca o token do usuário
        user_token = UserToken.objects.get(key=token_key)
        
        # Obtém parâmetros de filtragem
        operation_type = request.GET.get('type')
        status_filter = request.GET.get('status')
        limit = int(request.GET.get('limit', 20))
        
        # Inicializa a consulta base - filtrando por user_token
        query = Operation.objects.filter(user_token=user_token)
        
        # Aplica filtro por tipo de operação, se fornecido
        if operation_type:
            query = query.filter(operation_type=operation_type)
            
        # Aplica filtro por status, se fornecido
        if status_filter:
            query = query.filter(status=status_filter)
            
        # Limita o número de resultados e ordena por data de criação (mais recentes primeiro)
        query = query.order_by('-created_at')[:limit]
        
        # Converte os objetos do modelo para OperationData
        operations = [op.to_operation_data() for op in query]
        
        # Monta a resposta com resumo de cada operação
        response_data = {
            'success': True,
            'count': len(operations),
            'operations': [op.get_summary() for op in operations]
        }
        return JsonResponse(response_data, status=status.HTTP_200_OK)
        
    except UserToken.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido'
        }, status=status.HTTP_401_UNAUTHORIZED)
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': f"Parâmetro inválido: {str(e)}"
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"Erro ao listar operações: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f"Erro ao listar operações: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
