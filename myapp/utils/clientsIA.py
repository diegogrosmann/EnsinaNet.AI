from dotenv import load_dotenv
import os
from openai import OpenAI
import google.generativeai as genai
import markdown
import json

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class APIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def compare(self, system_messages: str) -> str:
        raise NotImplementedError("This method should be overridden in subclasses")

    def compareLabs(self, data: dict) -> dict:
        raise NotImplementedError("This method should be overridden in subclasses")
    
    def compareInstrucao(self, data: dict) -> dict:    
        raise NotImplementedError("This method should be overridden in subclasses")
    
    def _prepare_basic_system_messages(self) -> str:
        raise NotImplementedError("This method should be overridden in subclasses")

    def _prepare_answer_format(self) -> str:
        return '''
                Análise dos Arquivos de Configuração 
                    Erros Identificados: 
                        1. Linha X 
                            Erro: 
                            Configuração Correta: 
                            Sua Configuração: 
                        2. Linha Y 
                            Erro: 
                            Configuração Correta: 
                            Sua Configuração: 
                        3. (Faça isso para cada erro)
 
                Análise da Configuração da Rede 

                    Erros Identificados:  (Caso não tiver erros só exibir mensagem informando)
                        1.  Conexão X 
                            Erro: 
                            Configuração Correta: 
                            Sua Configuração: 
                        2.  Conexão Y 
                            Erro: 
                            Configuração Correta: 
                            Sua Configuração: 
                        3. (Faça isso para cada erro)

                Conteúdos para Estudar:  
                
                    Conteudo X 
                        Tópicos a Cobrir: 
                            Tópicos X: 
                            Tópicos Y: 
                        Recursos: 
                            Recurso X: 
                            Recurso Y: 

                    Conteudo Y 
                        Tópicos a Cobrir: 
                            Tópicos X: 
                            Tópicos Y: 
                        Recursos: 
                            Recurso X: 
                            Recurso Y: 

                    (Faça isso para cada conteúdo)

                Resumo: 
            '''


class ChatGPTClient(APIClient):
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        super().__init__(api_key)
        self.client = OpenAI(api_key=self.api_key)

    def _prepare_basic_system_messages(self):
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
                "content": f"""A resposta pode ser extruturada da seguinte forma:
                
                { self._prepare_answer_format() }
                """,
            },
        ]
    
    def compare(self, system_messages: str) -> str:
        try:
            response = self.client.chat.completions.create(            
                model="gpt-4o",
                messages=system_messages,
                temperature=0.1,
            )

            r = response.choices[0].message.content
            
            r = r.replace("\"", "**")
            rp = markdown.markdown(r, extensions=['fenced_code', 'def_list'])
            rp = rp.replace('\n', '').replace('\\n', '')
                
            return rp
        except Exception as e:
            return f"Erro ao comunicar com a API: {str(e)}"

    def compareLabs(self, data: dict) -> dict:     
        
        config_instrutor = json.dumps(data.get('config_instrutor'), indent=4)
        rede_instrutor = json.dumps(data.get('rede_instrutor'), indent=4)
        config_aluno = json.dumps(data.get('config_aluno'), indent=4)
        rede_aluno = json.dumps(data.get('rede_aluno'), indent=4)

        system_messages = self._prepare_basic_system_messages() + [
            {
                "role": "system",
                "content": "Você vai receber quatro informações, as configurações corretas dos equipamentos, as conexões da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede",
            },
            {
                "role": "system",
                "content": "Você deve comparar as configurações corretas com as que eu fiz. Com base nos erros que cometi você deve propor conteúdos para serem estudados.",
            },
            {
                "role": "user",
                "content": "Configuração Correta: \n" + config_instrutor,
            },
            {
                "role": "user",
                "content": "Rede Correta: \n" + rede_instrutor,
            },
            {
                "role": "user",
                "content": "Minha Configuração: \n" + config_aluno,
            },
            {
                "role": "user",
                "content": "Minha Rede: \n" + rede_aluno,
            },
            {
                "role": "user",
                "content": "Analise as configurações, identifique os erros e proponha conteúdos para estudar.",
            },
        ]
            
        return self.compare(system_messages)

    def compareInstrucao(self, data: dict) -> dict:     
        
        instrucao = json.dumps(data.get('instrucao'), indent=4)
        config_aluno = json.dumps(data.get('config_aluno'), indent=4)
        rede_aluno = json.dumps(data.get('rede_aluno'), indent=4)

        system_messages = self._prepare_basic_system_messages() + [
            {
                "role": "system",
                "content": "Você vai receber três informações, as instruções de configuração, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede",
            },
            {
                "role": "system",
                "content": "Você deve comparar as instruções com as configurações que eu fiz. Você deve analisar as minhas configurações, identificar erros e propor conteúdos para serem estudados.",
            },
            {
                "role": "user",
                "content": "Instruções: \n" + instrucao,
            },
            {
                "role": "user",
                "content": "Minha Configuração: \n" + config_aluno,
            },
            {
                "role": "user",
                "content": "Minha Rede: \n" + rede_aluno,
            },
            {
                "role": "user",
                "content": "Analise as configurações, identifique os erros e proponha conteúdos para estudar.",
            },
        ]

        return self.compare(system_messages)
    

class GeminiClient(APIClient):
    def __init__(self): 
        api_key = os.getenv('GEMINI_API_KEY')
        super().__init__(api_key)
        genai.configure(api_key=self.api_key)
    
    def compare(self, instruction: str, prompt: str) -> str:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro", 
            system_instruction=instruction
        )

        gemini_config = genai.types.GenerationConfig(
            temperature=0.2,
            top_k=10
        )

        m = model.generate_content(prompt, generation_config=gemini_config)
        r = m.text.replace("`", "")

        rp = markdown.markdown(r, extensions=['fenced_code', 'attr_list', 'def_list', 'sane_lists', 'nl2br', 'extra', 'codehilite'])
        rp = rp.replace('\n', '').replace('\\n', '')

        return rp

    def compareLabs(self, data: dict) -> dict:

        config_instrutor = json.dumps(data.get('config_instrutor'), indent=4)
        rede_instrutor = json.dumps(data.get('rede_instrutor'), indent=4)
        config_aluno = json.dumps(data.get('config_aluno'), indent=4)
        rede_aluno = json.dumps(data.get('rede_aluno'), indent=4)

        instruction = f'''
            Você deve atuar como um professor de Redes de Computadores.
            Você deve ter uma linguagem técnica e objetiva.
            Você vai receber quatro informações, as configurações corretas dos equipamentos, as conexões da rede, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
            Você deve comparar as configurações corretas com as que eu fiz. Com base nos erros que cometi você deve propor conteúdos para serem estudados.
            Você deve analisar o resultado dos comandos executados e não se eles são iguais e estão na mesma ordem.
            A resposta pode ser estruturada da seguinte forma:
                
            { self._prepare_answer_format() }    
        ''' 
                
        prompt = f'''
        Configuração Correta: 
        {config_instrutor}

        Rede Correta:
        {rede_instrutor}

        Minha Configuração:
        {config_aluno}

        Minha Rede: 
        {rede_aluno} 
        ''' 

        return self.compare(instruction, prompt)
        
    
    def compareInstrucao(self, data: dict) -> dict:

        instrucao = json.dumps(data.get('instrucao'), indent=4)
        config_aluno = json.dumps(data.get('config_aluno'), indent=4)
        rede_aluno = json.dumps(data.get('rede_aluno'), indent=4)

        instruction = f'''
            Você deve atuar como um professor de Redes de Computadores.
            Você deve ter uma linguagem técnica e objetiva.
            Você vai receber três informações, as instruções de configuração, as configurações que eu fiz nos equipamentos e as conexões que eu fiz na rede.
            Você deve comparar as instruções com as configurações que eu fiz. Você deve analisar as minhas configurações, identificar erros e propor conteúdos para serem estudados.
            A resposta pode ser estruturada da seguinte forma:
                
            { self._prepare_answer_format() }
        ''' 
                
        prompt = f'''
        Instruções: 
        {instrucao}

        Minha Configuração:
        {config_aluno}

        Minha Rede: 
        {rede_aluno} 
        ''' 
        
        return self.compare(instruction, prompt)