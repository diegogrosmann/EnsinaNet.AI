# Desenvolvimento no ComparadorIA

## Configuração
1. Clone e configure o ambiente virtual:
   ```bash
   git clone <URL_DO_REPO>
   cd ComparadorIA
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure `.env` e execute migrações:
   ```bash
   python manage.py migrate
   ```
3. Rode o servidor:
   ```bash
   python manage.py runserver
   ```

## Convenções de Código
- Utilize **docstrings** para todas as funções e classes.
- Siga o [PEP 8](https://www.python.org/dev/peps/pep-0008/).
- Utilize logs no diretório `logs/`.

## Testes
- **Testes Unitários**:
  ```bash
  python manage.py test
  ```
- **Geração da Documentação**:
  ```bash
  cd docs
  make html
  ```
