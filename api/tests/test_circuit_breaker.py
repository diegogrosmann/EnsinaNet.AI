# ai_config/tests/test_circuit_breaker.py

import time
from datetime import timedelta, datetime
from django.test import TestCase
from unittest.mock import patch, MagicMock
from core.exceptions import CircuitOpenError
from api.utils.circuit_breaker import (
    attempt_call,
    record_success,
    record_failure,
    get_status,
    reset_breaker,
    CircuitBreaker,
)
from core.types import CircuitState, CircuitBreakerConfig

class CircuitBreakerTest(TestCase):
    """Testes para a classe CircuitBreaker."""

    def setUp(self):
        """Configura o ambiente de testes."""
        # Instanciar o CircuitBreakerConfig sem o parâmetro randomness_factor
        config = CircuitBreakerConfig(
            service_name="test-service",
            failure_threshold=3,
            reset_timeout=1,
            success_threshold=2,
        )
        self.breaker = CircuitBreaker(config)
        self.api_name = "test-api"

    def test_can_execute_in_closed_state(self):
        """Verifica se o circuito fechado permite execução."""
        # Teste baseado no estado inicial (CLOSED)
        self.assertTrue(self.breaker.can_execute(self.api_name))
        
    def test_record_failure_and_open(self):
        """Testa se após falhas consecutivas o circuito abre e attempt_call dispara exceção."""
        # Registra falhas até ultrapassar o limite
        for _ in range(3):
            self.breaker.record_failure(self.api_name)
        
        # Verifica se o circuito abriu
        self.assertFalse(self.breaker.can_execute(self.api_name))
        
        # Testa a função attempt_call com o circuito aberto
        with patch('api.utils.circuit_breaker._circuit_breaker', self.breaker):
            with self.assertRaises(CircuitOpenError):
                attempt_call(self.api_name)

    def test_record_success_in_half_open_closes_circuit(self):
        """Simula o reset do circuito: após tempo de reset, uma tentativa com sucesso deve fechar o circuito."""
        # Abre o circuito
        for _ in range(3):
            self.breaker.record_failure(self.api_name)
        
        # Simula passagem do tempo de reset
        metrics = self.breaker._get_metrics(self.api_name)
        metrics.last_failure_time = datetime.now() - timedelta(seconds=2)
        
        # Agora o circuito deve estar em HALF_OPEN
        self.assertTrue(self.breaker.can_execute(self.api_name))
        self.assertEqual(metrics.state, CircuitState.HALF_OPEN)
        
        # Registra sucessos até fechar o circuito
        for _ in range(2):
            self.breaker.record_success(self.api_name)
        
        # Verifica se o circuito fechou
        self.assertEqual(metrics.state, CircuitState.CLOSED)
        self.assertTrue(self.breaker.can_execute(self.api_name))

    def test_get_status_and_reset(self):
        """Verifica se get_status retorna métricas e se reset_breaker reseta o estado."""
        # Registra algumas falhas e sucessos
        self.breaker.record_failure(self.api_name)
        self.breaker.record_success(self.api_name)
        
        # Verifica se get_status retorna as métricas corretas
        with patch('api.utils.circuit_breaker._circuit_breaker', self.breaker):
            status = get_status(self.api_name)
            self.assertIn(self.api_name, status)
            self.assertEqual(status[self.api_name]['state'], 'closed')
            
            # Testa o reset
            reset_breaker(self.api_name)
            
            # Verifica se o estado foi resetado
            status = get_status(self.api_name)
            self.assertEqual(status[self.api_name]['failure_count'], 0)
            self.assertEqual(status[self.api_name]['success_count'], 0)

# Fim de test_circuit_breaker.py
