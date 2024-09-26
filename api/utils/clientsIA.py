# myapp/utils/clientsIA.py

import os
import google.generativeai as genai
import json
import base64
import tempfile
import logging

from dotenv import load_dotenv
from openai import OpenAI
from django.conf import settings
from api.exceptions import FileProcessingError, APICommunicationError
from bs4 import BeautifulSoup

from google.cloud import documentai_v1 as documentai

# Configuração do logger
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Registry para armazenar os clientes de IA disponíveis
AVAILABLE_AI_CLIENTS = []

def register_ai_client(cls):
    """
    Decorador para registrar uma classe de cliente de IA no registry.
    """
    AVAILABLE_AI_CLIENTS.append(cls)
    return cls

def processar_documento(caminho_documento):
    """
    Processa o documento usando o Google Cloud Document AI e retorna o texto extraído.
    """
    logger.debug(f"Iniciando o processamento do documento: {caminho_documento}")

    # Configurações do Document AI
    project_id = 'doutorado-400019'  # Substitua pelo seu Project ID
    location = 'us'  # ou 'eu', dependendo da localização do processador
    processor_id = '6903f54add67ec8f'  # Substitua pelo seu Processor ID

    try:
        # Instanciar o cliente
        client = documentai.DocumentProcessorServiceClient()

        # Construir o caminho do processador
        nome_processador = client.processor_path(project_id, location, processor_id)

        # Ler o conteúdo do documento
        with open(caminho_documento, "rb") as f:
            conteudo_documento = f.read()

        # Definir o tipo MIME com base na extensão do arquivo
        _, ext = os.path.splitext(caminho_documento)
        ext = ext.lower()
        if ext == '.pdf':
            mime_type = 'application/pdf'
        elif ext in ['.png', '.jpg', '.jpeg']:
            mime_type = f'image/{ext[1:]}'
        else:
            mime_type = 'application/octet-stream'  # Tipo genérico

        # Criar a solicitação de processamento
        request = documentai.ProcessRequest(
            name=nome_processador,
            raw_document=documentai.RawDocument(content=conteudo_documento, mime_type=mime_type)
        )

        # Processar o documento
        resposta = client.process_document(request=request)
        texto_extraido = resposta.document.text
        logger.debug("Documento processado com sucesso.")
        return texto_extraido

    except Exception as e:
        logger.error(f"Erro ao processar o documento {caminho_documento}: {e}")
        raise FileProcessingError(f"Erro ao processar o documento: {e}")

def parsearHTML(html: str) -> str:
    """
    Parseia o HTML fornecido e retorna a div mais externa.
    
    :param html: String contendo o HTML a ser parseado.
    :return: String da div mais externa encontrada ou o HTML original se nenhuma div for encontrada.
    :raises ValueError: Se o HTML fornecido for inválido.
    """
    try:
        logger.debug("Iniciando o parseamento do HTML.")
        # Parsear o HTML com o BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Encontrar a div mais externa
        outer_div = soup.find('div')

        if outer_div:
            logger.debug("Div externa encontrada no HTML.")
            return str(outer_div)
        else:
            logger.warning("Nenhuma div encontrada no HTML. Retornando o HTML original.")
            return html
    except Exception as e:
        logger.error(f"Erro ao parsear o HTML: {e}")
        raise ValueError(f"Erro ao parsear o HTML: {e}")

class APIClient:
    """
    Classe base para clientes de API.
    Fornece métodos comuns para interação com APIs de IA.
    """

    def __init__(self, api_key: str = None, configurations: dict = None):
        """
        Inicializa o cliente de API com a chave fornecida e configurações.
        
        :param api_key: Chave de API para autenticação.
        :param configurations: Dicionário de configurações específicas.
        """
        self.api_key = api_key
        self.configurations = configurations or {}
        self.temp_file_paths = []
        self.uploaded_file_ids = []
        logger.debug(f"{self.__class__.__name__} inicializado com API key e configurações: {self.configurations}")

    def __enter__(self):
        """
        Método chamado ao entrar no contexto 'with'.
        """
        logger.debug(f"Entrando no contexto do {self.__class__.__name__}.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Método chamado ao sair do contexto 'with'.
        Realiza a limpeza dos arquivos temporários.
        """
        logger.debug(f"Saindo do contexto do {self.__class__.__name__}.")
        for temp_file_path in self.temp_file_paths:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Arquivo temporário deletado: {temp_file_path}")
                except Exception as e:
                    logger.error(f"Erro ao deletar o arquivo temporário {temp_file_path}: {e}")
                    raise FileProcessingError(f"Erro ao deletar o arquivo temporário {temp_file_path}: {e}")
        return False  # Não suprime exceções

    def compare(self, *args, **kwargs) -> str:
        """
        Método abstrato para comparação.
        Deve ser implementado nas subclasses.
        """
        raise NotImplementedError("Este método deve ser sobrescrito nas subclasses")

    def compare_labs(self, data: dict) -> dict:
        """
        Método abstrato para comparação de laboratórios.
        Deve ser implementado nas subclasses.
        """
        raise NotImplementedError("Este método deve ser sobrescrito nas subclasses")
    
    def compare_instruction(self, data: dict) -> dict:
        """
        Método abstrato para comparação com instruções.
        Deve ser implementado nas subclasses.
        """
        raise NotImplementedError("Este método deve ser sobrescrito nas subclasses")
    
    def compare_complete(self, data: dict) -> dict:
        """
        Método abstrato para comparação completa.
        Deve ser implementado nas subclasses.
        """
        raise NotImplementedError("Este método deve ser sobrescrito nas subclasses")
    
    def extract_file(self, instruction_data: dict) -> str: 
        """
        Extrai o arquivo de instruções enviado pelo usuário e o salva em um arquivo temporário.

        :param instruction_data: Dicionário com 'name' e 'content' do arquivo.
        :return: Caminho para o arquivo temporário criado.
        :raises FileProcessingError: Se ocorrer um erro no processamento do arquivo.
        """
        temp_file_path = ''

        if instruction_data is not None:
            name = instruction_data.get('name')
            content = instruction_data.get('content')

            if not name or not content:
                logger.error("Dados de instrução incompletos.")
                raise FileProcessingError("Dados de instrução incompletos.")

            try:
                # Decodifica o conteúdo do arquivo em Base64
                instruction_decoded = base64.b64decode(content)
                logger.debug("Conteúdo do arquivo decodificado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao decodificar o conteúdo do arquivo: {e}")
                raise FileProcessingError(f"Erro ao decodificar o conteúdo do arquivo: {e}")

            # Obtém a extensão do arquivo
            base_name, extension = os.path.splitext(name)
            
            try:
                # Cria um arquivo temporário para armazenar o conteúdo
                with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
                    temp_file.write(instruction_decoded)
                    temp_file_path = temp_file.name
                logger.info(f"Arquivo temporário criado: {temp_file_path}")
            except Exception as e:
                logger.error(f"Erro ao criar arquivo temporário: {e}")
                raise FileProcessingError(f"Erro ao criar arquivo temporário: {e}")

            # Armazena o caminho do arquivo temporário para posterior limpeza
            self.temp_file_paths.append(temp_file_path)

        return temp_file_path   

    def _prepare_basic_system_messages(self) -> str:
        """
        Método abstrato para preparar mensagens básicas do sistema.
        Deve ser implementado nas subclasses.
        """
        raise NotImplementedError("Este método deve ser sobrescrito nas subclasses")

    def _prepare_answer_format(self) -> str:
        """
        Prepara o formato da resposta carregando um arquivo HTML.
        
        :return: Conteúdo do arquivo de formato de resposta.
        :raises FileProcessingError: Se ocorrer um erro ao ler o arquivo.
        """
        file_path = os.path.join(settings.BASE_DIR, 'api', 'templates', 'resposta.html')
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            logger.debug("Formato de resposta carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao ler o arquivo de formato de resposta: {e}")
            raise FileProcessingError(f"Erro ao ler o arquivo de formato de resposta: {e}")
        return content

@register_ai_client
class ChatGPTClient(APIClient):
    """
    Cliente para interação com a API do ChatGPT.
    """
    name = "ChatGPT"  # Atributo para padronizar o nome na resposta

    def __init__(self, configurations=None):
        """
        Inicializa o cliente do ChatGPT com a chave de API e configurações.
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY não está definido nas variáveis de ambiente.")
            raise APICommunicationError("OPENAI_API_KEY não está definido nas variáveis de ambiente.")
        super().__init__(api_key, configurations)
        self.client = OpenAI(api_key=self.api_key)
        logger.debug("ChatGPTClient inicializado com configurações: {}".format(self.configurations))

    def __enter__(self):
        """
        Método chamado ao entrar no contexto 'with'.
        """
        logger.debug("Entrando no contexto do ChatGPTClient.")
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Método chamado ao sair do contexto 'with'.
        Realiza a limpeza de arquivos carregados na API.
        """
        logger.debug("Saindo do contexto do ChatGPTClient.")
        for file_id in self.uploaded_file_ids:
            try:
                self.client.files.delete(file_id)
                logger.info(f"Arquivo carregado deletado: {file_id}")
            except Exception as e:
                logger.error(f"Erro ao deletar o arquivo carregado {file_id}: {e}")
                raise APICommunicationError(f"Erro ao deletar o arquivo carregado {file_id}: {e}")
        super().__exit__(exc_type, exc_value, traceback)
        return False  # Não suprime exceções

    def _prepare_basic_system_messages(self):
        """
        Prepara as mensagens básicas do sistema para a interação com o ChatGPT.
        
        :return: Lista de dicionários representando mensagens do sistema.
        :raises APICommunicationError: Se ocorrer um erro ao preparar o formato da resposta.
        """
        try:
            answer_format = self._prepare_answer_format()
        except FileProcessingError as e:
            logger.error(f"Erro ao preparar o formato da resposta: {e}")
            raise APICommunicationError(f"Erro ao preparar o formato da resposta: {e}")

        return [
            {
                "role": "system",
                "content": "Você deve atuar como um professor de Redes de Computadores.",
            },
            {
                "role": "system",
                "content": "Você deve ter uma linguagem técnica e objetiva.",
            },
            {
                "role": "system",
                "content": f"""A resposta pode ser estruturada da seguinte forma:
                    
                    {answer_format}
                    """,
            },
            {
                "role": "system",
                "content": "A resposta deve ser formatada em HTML. Toda a resposta deve estar dentro da tag <div>.",
            },
        ]

    def compare(self, system_messages: list) -> str:
        """
        Realiza a comparação usando o ChatGPT.

        :param system_messages: Lista de mensagens para o sistema.
        :return: Resposta gerada pelo ChatGPT.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do ChatGPT.
        """
        try:
            logger.debug("Iniciando comparação com ChatGPT.")

            self.configurations['model'] = self.configurations.get('model', 'gpt-4')
            self.configurations['messages'] = system_messages

            response = self.client.chat.completions.create(
                **self.configurations
            )

            logger.debug("Chat criado e concluído com sucesso.")

            if not response:
                logger.error("Nenhuma mensagem retornada pelo ChatGPT.")
                raise APICommunicationError("Nenhuma mensagem retornada pelo ChatGPT.")

            logger.debug("Mensagens recuperadas com sucesso.")
            # Utiliza o método parsearHTML
            return parsearHTML(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Erro ao comunicar com a API ChatGPT: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API ChatGPT: {e}")

    # Os métodos compare_labs, compare_instruction e compare_complete permanecem inalterados
    # ...

@register_ai_client
class GeminiClient(APIClient):
    """
    Cliente para interação com a API do Gemini.
    """
    name = "Gemini"  # Atributo para padronizar o nome na resposta

    def __init__(self, configurations=None):
        """
        Inicializa o cliente do Gemini com a chave de API e configurações.
        """
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY não está definido nas variáveis de ambiente.")
            raise APICommunicationError("GEMINI_API_KEY não está definido nas variáveis de ambiente.")
        super().__init__(api_key, configurations)
        genai.configure(api_key=self.api_key)
        logger.debug("GeminiClient inicializado com configurações: {}".format(self.configurations))

    def __enter__(self):
        """
        Método chamado ao entrar no contexto 'with'.
        """
        logger.debug("Entrando no contexto do GeminiClient.")
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Método chamado ao sair do contexto 'with'.
        Realiza a limpeza de arquivos carregados na API.
        """
        logger.debug("Saindo do contexto do GeminiClient.")
        for file_id in self.uploaded_file_ids:
            try:
                genai.delete_file(file_id)
                logger.info(f"Arquivo carregado deletado: {file_id.name}")
            except Exception as e:
                logger.error(f"Erro ao deletar o arquivo carregado {file_id.name}: {e}")
                raise APICommunicationError(f"Erro ao deletar o arquivo carregado {file_id.name}: {e}")
        super().__exit__(exc_type, exc_value, traceback)
        return False  # Não suprime exceções

    def _prepare_basic_system_messages(self):
        """
        Prepara as mensagens básicas do sistema para a interação com o Gemini.
        
        :return: String contendo as instruções básicas para o Gemini.
        :raises APICommunicationError: Se ocorrer um erro ao preparar o formato da resposta.
        """
        try:
            answer_format = self._prepare_answer_format()
        except FileProcessingError as e:
            logger.error(f"Erro ao preparar o formato da resposta: {e}")
            raise APICommunicationError(f"Erro ao preparar o formato da resposta: {e}")

        return f'''
            Você deve atuar como um professor de Redes de Computadores.
            Você deve ter uma linguagem técnica e objetiva.
            Vão ser repassadas configurações de rede. Você deve analisar as configurações de acordo com as orientações.
            Você deve analisar se as configurações estão corretas, quais os erros cometidos, como corrigir os erros e propor conteúdos para serem estudados.
            Você deve analisar o resultado dos comandos executados e não se eles são iguais e estão na mesma ordem.
            A resposta pode ser estruturada da seguinte forma:
                {answer_format}
            A resposta deve ser formatada em HTML. Toda a resposta deve estar dentro da tag <div>.
            '''

    def compare(self, instruction: str, prompt: str, instruction_file_path: str = None) -> str:
        """
        Realiza a comparação usando o Gemini.

        :param instruction: Instruções do sistema.
        :param prompt: Prompt para geração de conteúdo.
        :param instruction_file_path: Caminho para o arquivo de instruções (opcional).
        :return: Resposta gerada pelo Gemini.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do Gemini.
        """
        try:
            if 'model_name' in self.configurations:
                _model_name = self.configurations.get('model_name')
                self.configurations.pop('model_name')
            else:
                _model_name = "gemini-1.5-pro"

            logger.debug("Iniciando comparação com Gemini.")
            
            model = genai.GenerativeModel(
                model_name=_model_name, 
                system_instruction=instruction
            )   

            logger.debug("Modelo Gemini configurado.")

            gemini_config = genai.types.GenerationConfig(
                **self.configurations
            )
            logger.debug("Configuração de geração definida.")

            inputs = [prompt]

            if instruction_file_path is not None:
                try:
                    # Faz o upload do arquivo e armazena o ID
                    file_id = genai.upload_file(path=instruction_file_path, display_name='Instruções de Configuração')
                    self.uploaded_file_ids.append(file_id)
                    inputs.append(file_id)
                    logger.info(f"Arquivo de instruções carregado com sucesso. ID: {file_id.name}")
                except Exception as e:
                    logger.error(f"Erro ao fazer upload do arquivo para Gemini: {e}")
                    raise APICommunicationError(f"Erro ao fazer upload do arquivo para Gemini: {e}")

            m = model.generate_content(inputs, generation_config=gemini_config)
            logger.debug("Conteúdo gerado com sucesso.")

            # Utiliza o método parsearHTML
            return parsearHTML(m.text)
        except Exception as e:
            logger.error(f"Erro ao comunicar com a API Gemini: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API Gemini: {e}")

    # Os métodos compare_labs, compare_instruction e compare_complete permanecem inalterados
    # ...
