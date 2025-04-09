"""View para comparação de dados usando múltiplas IAs."""

import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework import status
from django.http import HttpRequest, HttpResponse

from core.types import (
    APPResponse,
    APPError,
    EntityStatus
)

from api.service.comparator import compare_data

logger = logging.getLogger(__name__)

@api_view(['POST'])
def compare(request: HttpRequest) -> HttpResponse:
    """
    Endpoint para comparação de dados usando múltiplas IAs de forma SÍNCRONA.
    
    - Recebe dados de instrutor e alunos via POST;
    - Executa o processamento de comparação de forma síncrona;
    - Retorna a operação consolidada (OperationData) com status COMPLETED ou erro.
    """
    version = request.version
    logger.info(f"Iniciando operação compare (API v{version})")
    
    # Extrai e valida token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    
    try:
        # Executa o processamento síncrono
        operation_data = compare_data(data=request.data, token_key=token_key, sync=True)

        # Verifica o status da operação
        if operation_data.get_status() == EntityStatus.COMPLETED:
            # Monta o resumo consolidado da operação
            summary = operation_data.get_summary()
            # Retorna com sucesso, incluindo a operação consolidada
            response = APPResponse.create_success(summary)
            return JsonResponse(response.to_dict(), status=status.HTTP_200_OK)
        else:
            # Caso não esteja concluída, capturamos possíveis erros
            error_msg = f"Processamento não completado com sucesso. Status: {operation_data.get_status()}"
            error = operation_data.get_error()
            if error:
                error_msg += f". Erro: {error}"

            # Mesmo em caso de falha, retornamos o resumo da operação
            summary = operation_data.get_summary()
            app_error = APPError(message=error_msg)
            response = APPResponse.create_failure(app_error)
            return JsonResponse(response.to_dict(), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        # Captura qualquer exceção inesperada e retorna 500
        response = APPResponse.from_exception(e)
        return JsonResponse(response.to_dict(), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def compare_async(request: HttpRequest) -> HttpResponse:
    """
    Endpoint para comparação de dados usando múltiplas IAs de forma ASSÍNCRONA.
    
    - Recebe dados de instrutor e alunos via POST;
    - Cria uma operação de longa duração, porém não espera a conclusão;
    - Retorna o resumo inicial da operação (podendo ser acompanhada via operation_status).
    """
    version = request.version
    logger.info(f"Iniciando operação de comparação assíncrona (API v{version})")
    
    # Extrai e valida token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    
    try:
        # Cria a operação assíncrona
        operation_data = compare_data(data=request.data, token_key=token_key, sync=False)
        
        # Retornamos o resumo da operação imediatamente
        summary = operation_data.get_summary()
        response = APPResponse.create_success(summary)
        return JsonResponse(response.to_dict(), status=status.HTTP_200_OK)
    
    except Exception as e:
        # Captura qualquer exceção inesperada
        response = APPResponse.from_exception(e)
        return JsonResponse(response.to_dict(), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
