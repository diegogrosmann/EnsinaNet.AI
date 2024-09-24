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
from myapp.exceptions import FileProcessingError, APICommunicationError
from bs4 import BeautifulSoup

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

class APIClient:
    """
    Classe base para clientes de API.
    Fornece métodos comuns para interação com APIs de IA.
    """

    def __init__(self, api_key: str):
        """
        Inicializa o cliente de API com a chave fornecida.
        
        :param api_key: Chave de API para autenticação.
        """
        self.api_key = api_key
        self.temp_file_paths = []
        self.uploaded_file_ids = []
        logger.debug(f"{self.__class__.__name__} inicializado com API key.")

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
        file_path = os.path.join(settings.BASE_DIR, 'myapp', 'templates', 'resposta.html')
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            logger.debug("Formato de resposta carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao ler o arquivo de formato de resposta: {e}")
            raise FileProcessingError(f"Erro ao ler o arquivo de formato de resposta: {e}")
        return content

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

    @staticmethod
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

@register_ai_client
class ChatGPTClient(APIClient):
    """
    Cliente para interação com a API do ChatGPT.
    """
    name = "ChatGPT"  # Atributo para padronizar o nome na resposta

    def __init__(self):
        """
        Inicializa o cliente do ChatGPT com a chave de API.
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY não está definido nas variáveis de ambiente.")
            raise APICommunicationError("OPENAI_API_KEY não está definido nas variáveis de ambiente.")
        super().__init__(api_key)
        self.client = OpenAI(api_key=self.api_key)
        logger.debug("ChatGPTClient inicializado.")

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
                "role": "assistant",
                "content": "Você deve atuar como um professor de Redes de Computadores.",
            },
            {
                "role": "assistant",
                "content": "Você deve ter uma linguagem técnica e objetiva.",
            },
            {
                "role": "assistant",
                "content": f"""A resposta pode ser estruturada da seguinte forma:
                    
                    {answer_format}
                    """,
            },
            {
                "role": "assistant",
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
            
            #assistant = self.client.beta.assistants.create(
            #    name="Assistente de correção de atividade",
            #    model="gpt-4o",
            #    tools=[{"type": "file_search"}],
            #)

            assistant = self.client.beta.assistants.retrieve("asst_kxXv5KceBgLYoW95WNtJiKxH")
            logger.debug("Assistente criado com sucesso.")

            thread = self.client.beta.threads.create(
                messages=system_messages
            )
            logger.debug("Thread criada com sucesso.")

            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread.id, assistant_id=assistant.id
            )
            logger.debug("Run criado e concluído com sucesso.")

            messages = list(self.client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

            if not messages:
                logger.error("Nenhuma mensagem retornada pelo ChatGPT.")
                raise APICommunicationError("Nenhuma mensagem retornada pelo ChatGPT.")
            
            logger.debug("Mensagens recuperadas com sucesso.")
            # Utiliza o método estático parsearHTML
            return self.parsearHTML(messages[0].content[0].text.value)

        except Exception as e:
            logger.error(f"Erro ao comunicar com a API ChatGPT: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API ChatGPT: {e}")

    def compare_labs(self, data: dict) -> dict:
        """
        Compara as configurações do laboratório com as configurações do aluno usando o ChatGPT.

        :param data: Dicionário com os dados de configuração.
        :return: Dicionário contendo a resposta gerada pelo ChatGPT.
        :raises FileProcessingError: Se ocorrer um erro na serialização dos dados.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do ChatGPT.
        """
        try:
            instructor_config = json.dumps(data['instructor_config'], indent=4)
            instructor_network = json.dumps(data['instructor_network'], indent=4)
            student_config = json.dumps(data['student_config'], indent=4)
            student_network = json.dumps(data['student_network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        system_messages = self._prepare_basic_system_messages() + [
            {
                "role": "assistant",
                "content": "Você vai receber quatro informações: as configurações corretas dos equipamentos, as conexões da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.",
            },
            {
                "role": "assistant",
                "content": "Você deve comparar as configurações corretas com as que eu fiz. Com base nos erros que cometi, você deve propor conteúdos para serem estudados.",
            },
            {
                "role": "user",
                "content": "Configuração Correta: \n" + instructor_config,
            },
            {
                "role": "user",
                "content": "Rede Correta: \n" + instructor_network,
            },
            {
                "role": "user",
                "content": "Minha Configuração: \n" + student_config,
            },
            {
                "role": "user",
                "content": "Minha Rede: \n" + student_network,
            },
            {
                "role": "user",
                "content": "Analise as configurações, identifique os erros e proponha conteúdos para estudar.",
            },
        ]
        logger.debug("System messages preparadas para compare_labs.")
            
        comparison_result = self.compare(system_messages)
        return {"response": comparison_result}

    def compare_instruction(self, data: dict) -> dict:
        """
        Compara as instruções fornecidas com as configurações realizadas pelo aluno usando o ChatGPT.

        :param data: Dicionário com os dados de configuração e instruções.
        :return: Dicionário contendo a resposta gerada pelo ChatGPT.
        :raises FileProcessingError: Se ocorrer um erro na serialização dos dados.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do ChatGPT.
        """
        try:
            student_config = json.dumps(data['student_config'], indent=4)
            student_network = json.dumps(data['student_network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        try:
            instruction_file_path = self.extract_file(data['instruction'])
            logger.debug("Arquivo de instruções extraído com sucesso.")
        except FileProcessingError as e:
            logger.error(f"Erro ao extrair o arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao extrair o arquivo de instruções: {e}")

        try:
            # Faz o upload do arquivo de instruções para a API do OpenAI
            with open(instruction_file_path, "rb") as f:
                instructions = self.client.files.create(
                    file=f, purpose="assistants"
                )
            self.uploaded_file_ids.append(instructions.id)
            logger.info(f"Arquivo de instruções carregado com sucesso. ID: {instructions.id}")
        except Exception as e:
            logger.error(f"Erro ao fazer upload do arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao fazer upload do arquivo de instruções: {e}")

        system_messages = self._prepare_basic_system_messages() + [
            {
                "role": "assistant",
                "content": "Você vai receber três informações: as instruções de configuração, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.",
            },
            {
                "role": "assistant",
                "content": "Você deve comparar as instruções com as configurações que eu fiz. Você deve analisar as minhas configurações, identificar erros e propor conteúdos para serem estudados.",
            },
            {
                "role": "user",
                "content": "Instruções: \n",
                "attachments": [
                    { 
                        "file_id": instructions.id, 
                        "tools": [{"type": "file_search"}] 
                    }
                ],
            },
            {
                "role": "user",
                "content": "Minha Configuração: \n" + student_config,
            },
            {
                "role": "user",
                "content": "Minha Rede: \n" + student_network,
            },
            {
                "role": "user",
                "content": "Analise as configurações, identifique os erros e proponha conteúdos para estudar.",
            },
        ]
        logger.debug("System messages preparadas para compare_instruction.")

        comparison_result = self.compare(system_messages)
        return {"response": comparison_result}
    
    def compare_complete(self, data: dict) -> dict:
        """
        Compara as instruções, configurações do instrutor e do aluno, e redes usando o ChatGPT.

        :param data: Dicionário com 'instruction', 'instructor_config', 'instructor_network', 'student_config', 'student_network'.
        :return: Dicionário contendo a resposta gerada pelo ChatGPT.
        :raises FileProcessingError: Se ocorrer um erro na serialização dos dados ou no processamento do arquivo.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do ChatGPT.
        """
        try:
            instruction = data['instruction']
            instructor_config = json.dumps(data['instructor_config'], indent=4)
            instructor_network = json.dumps(data['instructor_network'], indent=4)
            student_config = json.dumps(data['student_config'], indent=4)
            student_network = json.dumps(data['student_network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados de entrada: {e}")
            raise FileProcessingError(f"Erro ao processar dados de entrada: {e}")

        try:
            instruction_file_path = self.extract_file(instruction)
            logger.debug("Arquivo de instruções extraído com sucesso.")
        except FileProcessingError as e:
            logger.error(f"Erro ao extrair o arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao extrair o arquivo de instruções: {e}")

        try:
            # Faz o upload do arquivo de instruções para a API do OpenAI
            with open(instruction_file_path, "rb") as f:
                instructions = self.client.files.create(
                    file=f, purpose="assistants"
                )
            self.uploaded_file_ids.append(instructions.id)
            logger.info(f"Arquivo de instruções carregado com sucesso. ID: {instructions.id}")
        except Exception as e:
            logger.error(f"Erro ao fazer upload do arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao fazer upload do arquivo de instruções: {e}")

        system_messages = self._prepare_basic_system_messages() + [
            {
                "role": "assistant",
                "content": "Você vai receber cinco informações: as instruções de configuração, as configurações corretas dos equipamentos, as conexões corretas da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.",
            },
            {
                "role": "assistant",
                "content": "Você deve comparar todas as informações fornecidas. Analise as instruções, as configurações corretas e as configurações realizadas, identifique erros, e proponha conteúdos para serem estudados.",
            },
            {
                "role": "user",
                "content": "Instruções: \n",
                "attachments": [
                    { 
                        "file_id": instructions.id,  # Ajustado para refletir a estrutura esperada
                        "tools": [{"type": "file_search"}] 
                    }
                ],
            },
            {
                "role": "user",
                "content": "Configuração Correta: \n" + instructor_config,
            },
            {
                "role": "user",
                "content": "Rede Correta: \n" + instructor_network,
            },
            {
                "role": "user",
                "content": "Minha Configuração: \n" + student_config,
            },
            {
                "role": "user",
                "content": "Minha Rede: \n" + student_network,
            },
            {
                "role": "user",
                "content": "Analise todas as informações, identifique os erros e proponha conteúdos para estudar.",
            },
        ]
        logger.debug("System messages preparadas para compare_complete.")

        comparison_result = self.compare(system_messages)
        return {"response": comparison_result}

@register_ai_client
class GeminiClient(APIClient):
    """
    Cliente para interação com a API do Gemini.
    """
    name = "Gemini"  # Atributo para padronizar o nome na resposta

    def __init__(self):
        """
        Inicializa o cliente do Gemini com a chave de API.
        """
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY não está definido nas variáveis de ambiente.")
            raise APICommunicationError("GEMINI_API_KEY não está definido nas variáveis de ambiente.")
        super().__init__(api_key)
        genai.configure(api_key=self.api_key)
        logger.debug("GeminiClient inicializado.")
    
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
            logger.debug("Iniciando comparação com Gemini.")
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro", 
                system_instruction=instruction
            )
            logger.debug("Modelo Gemini configurado.")

            gemini_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_k=10
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

            # Utiliza o método estático parsearHTML
            return self.parsearHTML(m.text)
        except Exception as e:
            logger.error(f"Erro ao comunicar com a API Gemini: {e}")
            raise APICommunicationError(f"Erro ao comunicar com a API Gemini: {e}")
        
    def compare_labs(self, data: dict) -> dict:
        """
        Compara as configurações do laboratório com as configurações do aluno usando o Gemini.

        :param data: Dicionário com os dados de configuração.
        :return: Dicionário contendo a resposta gerada pelo Gemini.
        :raises FileProcessingError: Se ocorrer um erro na serialização dos dados.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do Gemini.
        """
        try:
            instructor_config = json.dumps(data['instructor_config'], indent=4)
            instructor_network = json.dumps(data['instructor_network'], indent=4)
            student_config = json.dumps(data['student_config'], indent=4)
            student_network = json.dumps(data['student_network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        instruction = self._prepare_basic_system_messages()
        logger.debug("Instruções básicas preparadas.")
                
        prompt = f'''
        Você vai receber quatro informações: as configurações corretas dos equipamentos, as conexões corretas da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
        Você deve comparar as configurações corretas com as que eu fiz.

        Configuração Correta: 
        {instructor_config}

        Rede Correta:
        {instructor_network}

        Minha Configuração:
        {student_config}

        Minha Rede: 
        {student_network} 
        ''' 
        logger.debug("Prompt preparado para compare_labs.")

        comparison_result = self.compare(instruction, prompt)
        return {"response": comparison_result}
        
    def compare_instruction(self, data: dict) -> dict:
        """
        Compara as instruções fornecidas com as configurações realizadas pelo aluno usando o Gemini.

        :param data: Dicionário com os dados de configuração e instruções.
        :return: Dicionário contendo a resposta gerada pelo Gemini.
        :raises FileProcessingError: Se ocorrer um erro na serialização dos dados ou no processamento do arquivo.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do Gemini.
        """
        try:
            instruction_file_path = self.extract_file(data['instruction'])
            logger.debug("Arquivo de instruções extraído com sucesso.")
        except FileProcessingError as e:
            logger.error(f"Erro ao extrair o arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao extrair o arquivo de instruções: {e}")

        try:
            student_config = json.dumps(data['student_config'], indent=4)
            student_network = json.dumps(data['student_network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao serializar dados de configuração: {e}")
            raise FileProcessingError(f"Erro ao serializar dados de configuração: {e}")

        instruction = self._prepare_basic_system_messages()
        logger.debug("Instruções básicas preparadas.")
                
        prompt = f'''
        Você vai receber três informações: um arquivo com as instruções de configuração, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
        Você deve comparar as instruções com as configurações que eu fiz.
        
        Minha Configuração:
        {student_config}

        Minha Rede: 
        {student_network}  
        ''' 
        logger.debug("Prompt preparado para compare_instruction.")
        
        comparison_result = self.compare(instruction, prompt, instruction_file_path)
        return {"response": comparison_result}
    
    def compare_complete(self, data: dict) -> dict:
        """
        Compara as instruções, configurações do instrutor e do aluno, e redes usando o Gemini.

        :param data: Dicionário com 'instruction', 'instructor_config', 'instructor_network', 'student_config', 'student_network'.
        :return: Dicionário contendo a resposta gerada pelo Gemini.
        :raises FileProcessingError: Se ocorrer um erro na serialização dos dados ou no processamento do arquivo.
        :raises APICommunicationError: Se ocorrer um erro na comunicação com a API do Gemini.
        """
        try:
            instruction = data['instruction']
            instructor_config = json.dumps(data['instructor_config'], indent=4)
            instructor_network = json.dumps(data['instructor_network'], indent=4)
            student_config = json.dumps(data['student_config'], indent=4)
            student_network = json.dumps(data['student_network'], indent=4)
        except KeyError as e:
            logger.error(f"Chave ausente nos dados de entrada: {e}")
            raise FileProcessingError(f"Chave ausente nos dados de entrada: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados de entrada: {e}")
            raise FileProcessingError(f"Erro ao processar dados de entrada: {e}")

        try:
            instruction_file_path = self.extract_file(instruction)
            logger.debug("Arquivo de instruções extraído com sucesso.")
        except FileProcessingError as e:
            logger.error(f"Erro ao extrair o arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao extrair o arquivo de instruções: {e}")

        try:
            # Faz o upload do arquivo de instruções para a API do Gemini
            instructions = genai.upload_file(path=instruction_file_path, display_name='Instruções de Configuração')
            self.uploaded_file_ids.append(instructions)
            logger.info(f"Arquivo de instruções carregado com sucesso. ID: {instructions.name}")
        except Exception as e:
            logger.error(f"Erro ao fazer upload do arquivo de instruções: {e}")
            raise APICommunicationError(f"Erro ao fazer upload do arquivo de instruções: {e}")

        system_messages = self._prepare_basic_system_messages() + [
            {
                "role": "assistant",
                "content": "Você vai receber cinco informações: as instruções de configuração, as configurações corretas dos equipamentos, as conexões corretas da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.",
            },
            {
                "role": "assistant",
                "content": "Você deve comparar todas as informações fornecidas. Analise as instruções, as configurações corretas e as configurações realizadas, identifique erros, e proponha conteúdos para serem estudados.",
            },
            {
                "role": "user",
                "content": "Instruções: \n",
                "attachments": [
                    { 
                        "file_id": instructions.name,  # Ajustado para refletir a estrutura esperada
                        "tools": [{"type": "file_search"}] 
                    }
                ],
            },
            {
                "role": "user",
                "content": "Configuração Correta: \n" + instructor_config,
            },
            {
                "role": "user",
                "content": "Rede Correta: \n" + instructor_network,
            },
            {
                "role": "user",
                "content": "Minha Configuração: \n" + student_config,
            },
            {
                "role": "user",
                "content": "Minha Rede: \n" + student_network,
            },
            {
                "role": "user",
                "content": "Analise todas as informações, identifique os erros e proponha conteúdos para estudar.",
            },
        ]
        logger.debug("System messages preparadas para compare_complete.")

        comparison_result = self.compare(instruction, prompt=system_messages, instruction_file_path=instruction_file_path)
        return {"response": comparison_result}
