# Instalação do ComparadorIA

## Pré-requisitos
- **Python 3.9+**
- **pip** e **virtualenv** (recomendado)
- **Banco de dados** (SQLite para dev, PostgreSQL/MySQL para produção)

## Instalação
1. Clone o repositório:
   ```bash
   git clone <URL_DO_REPO>
   cd ComparadorIA
   ```
2. Crie um ambiente virtual e instale as dependências:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
3. Configure variáveis de ambiente `.env` e execute migrações:
   ```bash
   python manage.py migrate
   ```
4. Inicie o servidor:
   ```bash
   python manage.py runserver
   ```
