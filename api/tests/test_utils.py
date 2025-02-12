"""Testes para os utilitários da API.

Este módulo contém testes para os componentes utilitários da API, 
incluindo circuit breaker e outras ferramentas auxiliares.
"""

import unittest
from unittest.mock import patch
from pathlib import Path

from api.utils.circuit_breaker import (
    attempt_call,
    record_failure,
    record_success,
    CircuitOpenError,
    CIRCUIT_STATE
)
from api.constants import AIClientConfig
from api.exceptions import MissingAPIKeyError, APICommunicationError

class TestCircuitBreaker(unittest.TestCase):
    """Testes para o mecanismo de Circuit Breaker.
    
    Verifica o funcionamento do circuit breaker em diferentes cenários.
    """
    
    def setUp(self):
        """Prepara o ambiente para cada teste.
        
        Limpa o estado do circuit breaker antes de cada teste.
        """
        CIRCUIT_STATE.clear()

    def test_circuit_breaker_flow(self):
        """Testa o fluxo completo do circuit breaker.
        
        Verifica:
        1. Estado inicial (fechado)
        2. Registro de falhas
        3. Abertura do circuito
        4. Transição para meio-aberto
        5. Retorno ao estado fechado após sucesso
        """
        client_name = "TestClient"
        
        # Verifica estado inicial
        attempt_call(client_name)  # Não deve lançar exceção
        
        # Registra falhas
        for _ in range(3):
            record_failure(client_name)
        
        # Verifica abertura do circuito
        with self.assertRaises(CircuitOpenError):
            attempt_call(client_name)
        
        # Força timeout para testar half-open
        CIRCUIT_STATE[client_name]["opened_at"] = 0
        attempt_call(client_name)  # Deve permitir chamada
        record_success(client_name)  # Deve fechar o circuito
        
        # Confirma fechamento
        attempt_call(client_name)  # Não deve lançar exceção