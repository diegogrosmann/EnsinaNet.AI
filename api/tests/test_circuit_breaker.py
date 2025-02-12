"""Testes para o mecanismo de Circuit Breaker.

Este módulo contém testes que verificam o funcionamento do circuit breaker
que protege contra falhas em cascata nas chamadas às APIs.
"""

from django.test import TestCase
from api.utils.circuit_breaker import (
    attempt_call,
    record_failure,
    record_success,
    CIRCUIT_STATE,
    CircuitOpenError
)

class CircuitBreakerTest(TestCase):
    """Testes do mecanismo de Circuit Breaker.
    
    Verifica o comportamento e transições de estado do circuit breaker.
    """

    def setUp(self):
        """Prepara o ambiente para cada teste.
        
        Limpa o estado do circuit breaker antes de cada teste.
        """
        CIRCUIT_STATE.clear()
        self.client_name = "TestAI"

    def test_initial_state(self):
        """Testa o estado inicial do circuit breaker.
        
        Verifica se o circuito começa fechado e permite chamadas.
        """
        self.assertNotIn(self.client_name, CIRCUIT_STATE)
        # Primeiro uso deve criar o estado
        attempt_call(self.client_name)
        self.assertIn(self.client_name, CIRCUIT_STATE)
        self.assertEqual(CIRCUIT_STATE[self.client_name]["state"], "closed")

    def test_failure_threshold(self):
        """Testa o limite de falhas.
        
        Verifica se o circuito abre após atingir o limite de falhas.
        """
        client_name = "TestAI"
        
        # Registra falhas até o limite
        for _ in range(3):
            record_failure(client_name)
            
        # Verifica se o circuito abriu
        with self.assertRaises(CircuitOpenError):
            attempt_call(client_name)

    def test_timeout_reset(self):
        """Testa o reset por timeout.
        
        Verifica se o circuito muda para meio-aberto após o timeout.
        """
        client_name = "TestAI"
        
        # Força o circuito a abrir
        for _ in range(3):
            record_failure(client_name)
            
        # Força timeout
        CIRCUIT_STATE[client_name]["opened_at"] = 0
        
        # Deve permitir uma tentativa
        attempt_call(client_name)

    def test_success_closes_circuit(self):
        """Testa o fechamento após sucesso.
        
        Verifica se o circuito fecha após um sucesso em estado meio-aberto.
        """
        client_name = "TestAI"
        
        # Força circuito meio-aberto
        for _ in range(3):
            record_failure(client_name)
        CIRCUIT_STATE[client_name]["opened_at"] = 0
        
        # Registra sucesso e verifica fechamento
        record_success(client_name)
        attempt_call(client_name)  # Não deve lançar exceção
