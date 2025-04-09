"""Formulários para configuração e gerenciamento de IAs.

Este módulo contém formulários para configurar IAs, gerenciar tokens,
e processar arquivos de treinamento.
"""

import logging
import json
import bleach
from typing import Any, Dict
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, BaseFormSet, ModelChoiceField
from django.contrib.auth import get_user_model
from markdownx.widgets import MarkdownxWidget

from ai_config.exceptions import AIConfigException
from core.exceptions import FileProcessingException

from .models import (
    AIClientGlobalConfiguration, 
    AIClientConfiguration, 
    TokenAIConfiguration, 
    AITrainingFile, 
    TrainingCapture,
    UserToken
)

from api.utils.clientsIA import AI_CLIENT_MAPPING

logger = logging.getLogger(__name__)

API_CLIENT_CHOICES = [(ai_client, ai_client) for ai_client in AI_CLIENT_MAPPING.keys()]

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union({
    'p', 'br', 'strong', 'em', 'ul', 'ol', 'li',
    'table', 'tr', 'td', 'th', 'a', 'div', 
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section'
})
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}

User = get_user_model()

class BaseTrainingExampleFormSet(BaseFormSet):
    """Formset base para exemplos de treinamento.
    
    Agrega os recursos de mídia dos formulários individuais.
    """
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Inicializa o formset agregando mídia.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        try:
            super().__init__(*args, **kwargs)
            self.media = forms.Media()
            for form in self.forms:
                self.media += form.media
        except Exception as e:
            logger.error(f"Erro ao inicializar formset de treinamento: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário de treinamento: {e}")

class AIClientGlobalConfigForm(forms.ModelForm):
    """Formulário para criar/editar AIClientGlobalConfiguration.

    Adiciona o campo 'name' para nomear o cliente e 'api_url' como opcional.
    """
    api_client_class = forms.ChoiceField(
        choices=API_CLIENT_CHOICES,
        label='Classe do Cliente de API',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Selecione a classe do cliente de API.'
    )
    original_api_key = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = AIClientGlobalConfiguration
        fields = ['name', 'api_client_class', 'api_url', 'api_key']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário e aplica mascaramento na API key.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        try:
            super(AIClientGlobalConfigForm, self).__init__(*args, **kwargs)
            if self.instance and self.instance.api_key:
                masked_key = self.mask_api_key(self.instance.api_key)
                self.initial['api_key'] = masked_key
                self.initial['original_api_key'] = self.instance.api_key
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de configuração global: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário de configuração: {e}")

    def mask_api_key(self, api_key: str) -> str:
        """Mascara a chave de acesso à API para exibição.

        Args:
            api_key (str): Chave original.

        Returns:
            str: Chave mascarada.
        """
        try:
            if len(api_key) > 8:
                return f"{api_key[:4]}****{api_key[-4:]}"
            else:
                return '*' * len(api_key)
        except Exception as e:
            logger.error(f"Erro ao mascarar API key: {e}", exc_info=True)
            return "****"

    def clean_api_key(self) -> str:
        """Processa o campo 'api_key' para retornar o valor correto.

        Retorna a chave original se o valor não tiver sido alterado.

        Returns:
            str: API key válida.
        """
        try:
            api_key = self.cleaned_data.get('api_key')
            original_api_key = self.initial.get('original_api_key')
            masked_key = self.mask_api_key(original_api_key) if original_api_key else ''
            
            if api_key == masked_key:
                return original_api_key
            else:
                return api_key
        except Exception as e:
            logger.error(f"Erro ao limpar API key: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar a chave de API: {e}")

class AIClientConfigurationForm(forms.ModelForm):
    """Formulário para criação/edição de AIClientConfiguration."""
    
    name = forms.CharField(
        label='Nome',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        }),
        help_text='Insira o nome da configuração.',
        required=True
    )

    ai_client = forms.ModelChoiceField(
        queryset=AIClientGlobalConfiguration.objects.all(),
        widget=forms.Select(
            attrs={'class': 'form-select'}
        ),
        help_text='Selecione a API a ser utilizada.',
        required=True
    )

    model_name = forms.CharField(
        label='Modelo',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        }),
        help_text='Insira o nome do Modelo.',
        required=True
    )

    use_system_message = forms.CharField(
        label='Usar Mensagem de Sistema',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Selecione se o modelo suporta mensagem de sistema.',
        required=True
    )    

    configurations = forms.CharField(
        label='Configurações',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Exemplo:\ntemperature=0.2\ntop_k=10'
        }),
        help_text='Insira os parâmetros no formato chave=valor, um por linha.',
        required=False
    )

    training_configurations = forms.CharField(
        label='Configurações de Treinamento',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Exemplo:\nbatch_size=4\nepochs=3'
        }),
        help_text='Insira os parâmetros no formato chave=valor, um por linha.',
        required=False
    )

    class Meta:
        model = AIClientConfiguration
        fields = ['name', 'ai_client', 'model_name', 'configurations', 'training_configurations', 'use_system_message']


    def __init__(self, *args, **kwargs):
        """Inicializa o formulário e converte os dados existentes do JSON para texto multiline.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        try:
            super().__init__(*args, **kwargs)

            # Inicializa campos de configuração como strings vazias por padrão
            self.initial['configurations'] = ""
            self.initial['training_configurations'] = ""

            # Processa configurations
            if self.instance and self.instance.configurations:
                if isinstance(self.instance.configurations, dict) and len(self.instance.configurations) > 0:
                    lines = []
                    for k, v in self.instance.configurations.items():
                        lines.append(f"{k}={v}")
                    self.initial['configurations'] = "\n".join(lines)               
            
            # Processa training_configurations
            if self.instance and self.instance.training_configurations:
                if isinstance(self.instance.training_configurations, dict) and len(self.instance.training_configurations) > 0:
                    lines = []
                    for k, v in self.instance.training_configurations.items():
                        lines.append(f"{k}={v}")
                    self.initial['training_configurations'] = "\n".join(lines)

            if self.instance and not self.instance._state.adding and self.instance.ai_client_id:
                client_class = AI_CLIENT_MAPPING.get(self.instance.ai_client.api_client_class)
                if client_class and not getattr(client_class, "supports_system_message", False):
                    self.fields['use_system_message'].initial = False
                    self.fields['use_system_message'].disabled = True
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de configuração de cliente: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário: {e}")

    def clean(self) -> Dict[str, Any]:
        """Valida o formulário garantindo consistência com a classe da API.
        
        Returns:
            Dict[str, Any]: Dados limpos e validados.
        """
        try:
            cleaned_data = super().clean()
            ai_client = cleaned_data.get('ai_client')
            
            # Valida o uso de system_message com base no cliente de API
            if ai_client:
                client_class = AI_CLIENT_MAPPING.get(ai_client.api_client_class)
                if client_class and not getattr(client_class, "supports_system_message", False):
                    cleaned_data['use_system_message'] = False
                    
            return cleaned_data
        except Exception as e:
            logger.error(f"Erro ao validar formulário de configuração de cliente: {e}", exc_info=True)
            raise ValidationError(f"Erro ao validar configuração: {e}")

    def clean_name(self) -> str:
        """Valida que o campo 'name' não esteja vazio nem contenha espaços em excesso.

        Returns:
            str: Nome validado.

        Raises:
            forms.ValidationError: Se o nome estiver vazio.
        """
        try:
            name = self.cleaned_data.get('name', '').strip()
            if not name:
                raise forms.ValidationError("Nome não pode ser vazio.")
            return name
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Erro ao validar nome: {e}", exc_info=True)
            raise ValidationError(f"Erro ao validar nome: {e}")

    def _convert_dictionary(self, field_name: str) -> Dict[str, Any]:
        """Converte um campo de texto para dicionário.

        Args:
            field_name (str): O nome do campo a ser limpo ('configurations' ou 'training_configurations').

        Returns:
            dict: Dicionário com as configurações.

        Raises:
            forms.ValidationError: Se alguma linha estiver no formato incorreto.
        """
        try:
            data = self.data.get(field_name) or ''
            data = data.strip()

            if data:
                config_dict = {}
                for line_number, line in enumerate(data.splitlines(), start=1):
                    line = line.strip()
                    if not line:
                        continue
                    if '=' not in line:
                        raise forms.ValidationError(
                            f"Linha {line_number}: '{line}' não está no formato chave=valor."
                        )
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if not key:
                        raise forms.ValidationError(
                            f"Linha {line_number}: Chave vazia."
                        )
                    if not value:
                        raise forms.ValidationError(
                            f"Linha {line_number}: Valor vazio para a chave '{key}'."
                        )

                    # Verificar se o valor parece ser um objeto JSON
                    if value.startswith('{') and value.endswith('}'):
                        try:
                            # Tentar interpretar como JSON
                            parsed_value = json.loads(value)
                            config_dict[key] = parsed_value
                            continue
                        except json.JSONDecodeError:
                            # Se falhar, tentar converter aspas simples para aspas duplas
                            try:
                                # Substituir aspas simples por aspas duplas, mas apenas para chaves e valores JSON
                                fixed_value = value.replace("'", '"')
                                parsed_value = json.loads(fixed_value)
                                config_dict[key] = parsed_value
                                continue
                            except json.JSONDecodeError as e:
                                # Formato JSON inválido mesmo após correção
                                raise forms.ValidationError(
                                    f"Linha {line_number}: Valor para chave '{key}' parece ser JSON mas está inválido: {e}. "
                                    f"Certifique-se de usar aspas duplas para chaves e valores no JSON."
                                )

                    # Processamento padrão para valores simples
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass

                    config_dict[key] = value
                return config_dict
            return {}
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Erro ao converter dicionário para o campo {field_name}: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar configurações: {e}")

    def clean_configurations(self) -> Dict[str, Any]:
        """Converte o campo 'configurations' de texto para dicionário.

        Returns:
            dict: Dicionário com as configurações.

        Raises:
            forms.ValidationError: Se alguma linha estiver no formato incorreto.
        """
        try:
            return self._convert_dictionary('configurations')
        except forms.ValidationError as e:
            # Relança o erro específico para este campo
            raise forms.ValidationError(
                f"Erro nas configurações: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Erro ao limpar configurações: {e}", exc_info=True)
            # Tratamento genérico para outros erros
            raise forms.ValidationError(
                "Formato inválido. Por favor, use o formato chave=valor, um por linha."
            )

    def clean_training_configurations(self) -> Dict[str, Any]:
        """Converte o campo 'training_configurations' de texto para dicionário.

        Returns:
            dict: Dicionário com as configurações de treinamento.

        Raises:
            forms.ValidationError: Se alguma linha estiver no formato incorreto.
        """
        try:
            return self._convert_dictionary('training_configurations')
        except forms.ValidationError as e:
            # Relança o erro específico para este campo
            raise forms.ValidationError(
                f"Erro nas configurações de treinamento: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Erro ao limpar configurações de treinamento: {e}", exc_info=True)
            # Tratamento genérico para outros erros
            raise forms.ValidationError(
                "Formato inválido. Por favor, use o formato chave=valor, um por linha."
            )

class TokenAIConfigurationForm(forms.ModelForm):
    """Formulário para criação/edição de TokenAIConfiguration."""
    base_instruction = forms.CharField(
        label='Instrução Base',
        widget=MarkdownxWidget(attrs={'class': 'form-control'}),
        required=False,
        help_text='Insira a instrução base personalizada para este token.'
    )
    prompt = forms.CharField(
        label='Prompt',
        widget=MarkdownxWidget(attrs={'class': 'form-control'}),
        required=False,
        help_text='Insira o prompt para todas as comparações.'
    )
    responses = forms.CharField(
        label='Respostas',
        widget=MarkdownxWidget(attrs={'class': 'form-control'}),
        required=False,
        help_text='Insira as respostas para todas as comparações.'
    )

    class Meta:
        model = TokenAIConfiguration
        fields = ['base_instruction', 'prompt', 'responses']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário definindo o queryset do campo 'training_file' conforme o usuário.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados, incluindo 'user' opcional.
        """
        try:
            user = kwargs.pop('user', None)
            super(TokenAIConfigurationForm, self).__init__(*args, **kwargs)
            self.user = user
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de configuração de token: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário de token: {e}")

    def clean_base_instruction(self) -> str:
        """Limpa e sanitiza o campo 'base_instruction'.

        Returns:
            str: Instrução base limpa.
        """
        try:
            base_instruction_html = self.cleaned_data.get('base_instruction', '').strip()
            return bleach.clean(base_instruction_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        except Exception as e:
            logger.error(f"Erro ao sanitizar instrução base: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar instrução base: {e}")

    def clean_prompt(self) -> str:
        """Limpa e sanitiza o campo 'prompt'.

        Returns:
            str: Prompt limpo.
        """
        try:
            prompt_html = self.cleaned_data.get('prompt', '').strip()
            return bleach.clean(prompt_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        except Exception as e:
            logger.error(f"Erro ao sanitizar prompt: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar prompt: {e}")

    def clean_responses(self) -> str:
        """Limpa e sanitiza o campo 'responses'.

        Returns:
            str: Respostas limpas.
        """
        try:
            responses_html = self.cleaned_data.get('responses', '').strip()
            return bleach.clean(responses_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        except Exception as e:
            logger.error(f"Erro ao sanitizar respostas: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar respostas: {e}")

class AITrainingFileNameForm(forms.Form):
    """Formulário para nomear um arquivo de treinamento."""
    name = forms.CharField(
        label='Nome do Arquivo de Treinamento',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Insira um nome para identificar facilmente este arquivo de treinamento.'
    )

class TrainingCaptureForm(forms.ModelForm):
    """Formulário para configurar uma captura de treinamento."""
    
    token = ModelChoiceField(
        queryset=UserToken.objects.none(),
        empty_label="Selecione um token",
        required=True
    )
    
    ai_client_config = forms.ModelChoiceField(
        queryset=AIClientConfiguration.objects.none(),
        empty_label="Selecione um cliente de IA",
        required=True
    )

    class Meta:
        model = TrainingCapture
        fields = ['token', 'ai_client_config']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário filtrando os querysets por usuário.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados, incluindo 'user' opcional.
        """
        try:
            user = kwargs.pop('user', None)
            super().__init__(*args, **kwargs)
            if user:
                self.fields['token'].queryset = UserToken.objects.filter(user=user)
                self.fields['ai_client_config'].queryset = AIClientConfiguration.objects.filter(user=user)
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de captura de treinamento: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário de captura: {e}")

class AITrainingFileForm(forms.ModelForm):
    """Formulário para upload de arquivo de treinamento."""
    class Meta:
        model = AITrainingFile
        fields = ['name']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_file(self) -> Any:
        """Realiza a limpeza e validação do arquivo enviado.

        Returns:
            Arquivo validado.
            
        Raises:
            ValidationError: Se o arquivo for inválido.
        """
        try:
            file = self.cleaned_data.get('file')
            return file
        except Exception as e:
            logger.error(f"Erro ao validar arquivo: {e}", exc_info=True)
            raise FileProcessingException(f"Erro ao processar arquivo: {e}")

class UserAITrainingFileForm(forms.ModelForm):
    """Formulário para upload de arquivo de treinamento vinculado ao usuário."""
    class Meta:
        model = AITrainingFile
        fields = []
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário, marcando o campo 'file' como obrigatório.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        try:
            super(UserAITrainingFileForm, self).__init__(*args, **kwargs)
            self.fields['file'].required = True
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de arquivo de treinamento: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário: {e}")

class TrainAIForm(forms.Form):
    """Formulário para seleção de IAs a serem treinadas."""
    ai_clients_to_train = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        label='Selecionar IAs para Treinar',
        required=True,
        help_text='Selecione as IAs que deseja treinar.',
    )

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário definindo as escolhas com base nos clientes de IA disponíveis.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados, incluindo 'ai_clients' opcional.
        """
        try:
            ai_clients = kwargs.pop('ai_clients', [])
            super(TrainAIForm, self).__init__(*args, **kwargs)
            self.fields['ai_clients_to_train'].choices = [(client.name, client.name) for client in ai_clients]
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de treinamento de IA: {e}", exc_info=True)
            raise AIConfigException(f"Erro ao preparar formulário de treinamento: {e}")

class TrainingExampleForm(forms.Form):
    """Formulário para exemplo de treinamento com mensagens do sistema e usuário."""
    system_message = forms.CharField(
        label='Mensagem do Sistema',
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
        required=False
    )
    user_message = forms.CharField(
        label='Mensagem do Usuário',
        widget=forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
        required=True
    )
    response = forms.CharField(
        label='Resposta',
        widget=MarkdownxWidget(attrs={
            'class': 'form-control markdownx-editor',
            'rows': 4,
            'placeholder': 'Digite a resposta em markdown...'
        }),
        required=True
    )

    def clean_user_message(self) -> str:
        """Substitui '\\n' por quebras de linha reais no campo 'user_message'.

        Returns:
            str: Mensagem do usuário formatada.
        """
        try:
            user_message = self.cleaned_data.get('user_message', '')
            return user_message.replace('\\n', '\n')
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do usuário: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar mensagem: {e}")

    def clean_system_message(self) -> str:
        """Substitui '\\n' por quebras de linha reais no campo 'system_message'.

        Returns:
            str: Mensagem do sistema formatada.
        """
        try:
            system_message = self.cleaned_data.get('system_message', '')
            return system_message.replace('\\n', '\n')
        except Exception as e:
            logger.error(f"Erro ao processar mensagem do sistema: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar mensagem do sistema: {e}")

    def clean_response(self) -> str:
        """Substitui '\\n' por quebras de linha reais no campo 'response'.

        Returns:
            str: Resposta formatada.
        """
        try:
            response = self.cleaned_data.get('response', '')
            return response.replace('\\n', '\n')
        except Exception as e:
            logger.error(f"Erro ao processar resposta: {e}", exc_info=True)
            raise ValidationError(f"Erro ao processar resposta: {e}")

TrainingExampleFormSetFactory = formset_factory(
    TrainingExampleForm,
    formset=BaseTrainingExampleFormSet,
    can_delete=True,
    extra=0
)
