"""
Módulo com classes base para views da API.

Fornece classes base com funcionalidades comuns para as views da API,
garantindo consistência no tratamento de requisições e respostas.
"""
import logging
from typing import Any, Dict, Optional, TypeVar, Generic, Type

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.types.api_response import APIResponse
from core.types.base import JSONDict
from core.exceptions import APIError

logger = logging.getLogger(__name__)

T = TypeVar('T')

class BaseAPIView(APIView):
    """Classe base para todas as views da API.
    
    Implementa funcionalidades comuns como formatação de respostas,
    tratamento de erros e logging.
    """
    
    def success_response(self, data: Optional[Any] = None, status_code: int = status.HTTP_200_OK) -> Response:
        """Cria uma resposta de sucesso padronizada.
        
        Args:
            data: Dados a serem incluídos na resposta.
            status_code: Código HTTP de status.
            
        Returns:
            Response: Resposta formatada para o cliente.
        """
        api_response = APIResponse.success_response(data)
        return Response(api_response.to_dict(), status=status_code)
    
    def error_response(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """Cria uma resposta de erro padronizada.
        
        Args:
            message: Mensagem de erro.
            status_code: Código HTTP de status.
            
        Returns:
            Response: Resposta formatada para o cliente.
        """
        api_response = APIResponse.error_response(message)
        return Response(api_response.to_dict(), status=status_code)
    
    def exception_response(self, exception: Exception, status_code: Optional[int] = None) -> Response:
        """Cria uma resposta a partir de uma exceção.
        
        Args:
            exception: Exceção ocorrida.
            status_code: Código HTTP de status (opcional, detectado automaticamente se for APIError).
            
        Returns:
            Response: Resposta formatada para o cliente.
        """
        api_response = APIResponse.from_exception(exception)
        
        # Determinar o status code apropriado
        response_status = status_code
        if response_status is None:
            if isinstance(exception, APIError):
                response_status = exception.status_code
            else:
                response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return Response(api_response.to_dict(), status=response_status)

class ModelAPIView(BaseAPIView, Generic[T]):
    """Classe base para views da API que lidam com modelos.
    
    Estende BaseAPIView com funcionalidades específicas para manipulação
    de modelos, como serialização e validação.
    
    Attributes:
        model_class: Classe do modelo Django associado à view.
        serializer_class: Classe do serializer para o modelo.
    """
    model_class: Optional[Type[T]] = None
    serializer_class: Optional[Type] = None
    
    def get_object(self, pk: Any) -> T:
        """Recupera um objeto do modelo pelo ID.
        
        Args:
            pk: Identificador primário do objeto.
            
        Returns:
            Instância do modelo.
            
        Raises:
            APIError: Se o objeto não for encontrado.
        """
        if self.model_class is None:
            raise APIError("Model class não definida", status_code=500)
            
        try:
            return self.model_class.objects.get(pk=pk)
        except self.model_class.DoesNotExist:
            raise APIError(f"Objeto {self.model_class.__name__} com ID {pk} não encontrado", 
                          status_code=status.HTTP_404_NOT_FOUND)
    
    def validate_serializer(self, data: JSONDict, partial: bool = False) -> Any:
        """Valida dados usando o serializer configurado.
        
        Args:
            data: Dados a serem validados.
            partial: Se True, permite atualizações parciais.
            
        Returns:
            Serializer validado.
            
        Raises:
            APIError: Se a validação falhar.
        """
        if self.serializer_class is None:
            raise APIError("Serializer class não definida", status_code=500)
            
        serializer = self.serializer_class(data=data, partial=partial)
        if not serializer.is_valid():
            errors = serializer.errors
            error_msg = "Dados inválidos"
            if errors:
                error_details = []
                for field, field_errors in errors.items():
                    error_details.append(f"{field}: {', '.join(field_errors)}")
                error_msg = f"Dados inválidos: {'; '.join(error_details)}"
                
            raise APIError(error_msg, status_code=status.HTTP_400_BAD_REQUEST)
            
        return serializer
