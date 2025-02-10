# Uso do ComparadorIA

## Autenticação e Tokens
1. **Registro/Login**: Acesse `/accounts/register/` e `/accounts/login/`.
2. **Gerenciamento de Tokens**: `/accounts/manage-tokens/` para criar e visualizar tokens.
3. **Uso na API**: Inclua `Authorization: Token <seu_token>` no header.

## Configuração de IA
- Gerenciar configurações via `/ai-config/`.
- Upload de arquivos para treinamento `/ai-config/upload/`.
- Configurar parâmetros de IA para cada token.

## API
### Endpoint `/api/compare/`
- **Método**: `POST`
- **JSON**:
  ```json
  {
    "instructor": { "instruction": "Texto...", ... },
    "students": { "aluno1": { ... } }
  }
  ```
- **Teste com cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/compare/        -H "Authorization: Token SEU_TOKEN"        -H "Content-Type: application/json"        -d '{ "instructor": { "instruction": "Teste" }, "students": {} }'
  ```
