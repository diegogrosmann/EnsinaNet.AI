"""Formulários para a aplicação de configuração de IA.

Contém classes de formulários para criação e edição de configurações, treinamento, arquivos
e processamento dos dados relativos à IA.
"""

import json
import bleach
from django import forms
from django.forms import formset_factory, BaseFormSet, ModelChoiceField
from django.contrib.auth import get_user_model
from markdownx.widgets import MarkdownxWidget

from .models import (
    AIClientGlobalConfiguration, 
    AIClientConfiguration, 
    TokenAIConfiguration, 
    AITrainingFile, 
    AIClientTraining, 
    TrainingCapture,
    UserToken
)

from api.utils.clientsIA import AI_CLIENT_MAPPING

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

    Responsável por agregar os media dos formulários.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media = forms.Media()
        for form in self.forms:
            self.media += form.media

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
        super(AIClientGlobalConfigForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.api_key:
            masked_key = self.mask_api_key(self.instance.api_key)
            self.initial['api_key'] = masked_key
            self.initial['original_api_key'] = self.instance.api_key

    def mask_api_key(self, api_key):
        """Mascara a chave de acesso à API para exibição.

        Args:
            api_key (str): Chave original.

        Returns:
            str: Chave mascarada.
        """
        if len(api_key) > 8:
            return f"{api_key[:4]}****{api_key[-4:]}"
        else:
            return '*' * len(api_key)

    def clean_api_key(self):
        """Processa o campo 'api_key' para retornar o valor correto.

        Retorna a chave original se o valor não tiver sido alterado.

        Returns:
            str: API key válida.
        """
        api_key = self.cleaned_data.get('api_key')
        original_api_key = self.initial.get('original_api_key')
        masked_key = self.mask_api_key(original_api_key) if original_api_key else ''
        
        if api_key == masked_key:
            return original_api_key
        else:
            return api_key

class AIClientConfigurationForm(forms.ModelForm):
    """Formulário para criação/edição de AIClientConfiguration.

    Converte o campo 'configurations' de dicionário para um formato 'key=value' multiline.
    """
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

    class Meta:
        model = AIClientConfiguration
        fields = ['name', 'ai_client', 'enabled', 'model_name', 'configurations', 'use_system_message']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário e converte os dados existentes do JSON para texto multiline."""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.configurations:
            if isinstance(self.instance.configurations, dict) and len(self.instance.configurations) > 0:
                lines = []
                for k, v in self.instance.configurations.items():
                    lines.append(f"{k}={v}")
                self.initial['configurations'] = "\n".join(lines)
            else:
                self.initial['configurations'] = ""
        else:
            self.initial['configurations'] = ""
        
        if self.instance and not self.instance._state.adding and self.instance.ai_client_id:
            client_class = AI_CLIENT_MAPPING.get(self.instance.ai_client.api_client_class)
            if client_class and not getattr(client_class, "supports_system_message", False):
                self.fields['use_system_message'].initial = False
                self.fields['use_system_message'].disabled = True

    def clean(self):
        """Valida o formulário garantindo consistência com a classe da API."""
        cleaned_data = super().clean()
        ai_client = cleaned_data.get('ai_client')
        if ai_client:
            client_class = AI_CLIENT_MAPPING.get(ai_client.api_client_class)
            if client_class and not getattr(client_class, "supports_system_message", False):
                cleaned_data['use_system_message'] = False
        return cleaned_data
    
    def clean_name(self):
        """Valida que o campo 'name' não esteja vazio nem contenha espaços em excesso.

        Returns:
            str: Nome validado.

        Raises:
            forms.ValidationError: Se o nome estiver vazio.
        """
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Nome não pode ser vazio.")
        return name

    def clean_configurations(self):
        """Converte o campo 'configurations' de texto para dicionário.

        Retorna:
            dict: Dicionário com as configurações.

        Raises:
            forms.ValidationError: Se alguma linha estiver no formato incorreto.
        """
        data = self.cleaned_data.get('configurations', '').strip()
        config_dict = {}

        if data:
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

                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass

                config_dict[key] = value

        return config_dict
    
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
    training_file = forms.ModelChoiceField(
        queryset=AITrainingFile.objects.none(),
        required=False,
        label='Arquivo de Treinamento',
        help_text='Selecione o arquivo de treinamento para este token.'
    )

    class Meta:
        model = TokenAIConfiguration
        fields = ['base_instruction', 'prompt', 'responses', 'training_file']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário definindo o queryset do campo 'training_file' conforme o usuário."""
        user = kwargs.pop('user', None)
        super(TokenAIConfigurationForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['training_file'].queryset = AITrainingFile.objects.filter(user=user)
        self.user = user

    def clean_base_instruction(self):
        """Limpa e sanitiza o campo 'base_instruction'.

        Returns:
            str: Instrução base limpa.
        """
        base_instruction_html = self.cleaned_data.get('base_instruction', '').strip()
        return bleach.clean(base_instruction_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_prompt(self):
        """Limpa e sanitiza o campo 'prompt'.

        Returns:
            str: Prompt limpo.
        """
        prompt_html = self.cleaned_data.get('prompt', '').strip()
        return bleach.clean(prompt_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_responses(self):
        """Limpa e sanitiza o campo 'responses'.

        Returns:
            str: Respostas limpas.
        """
        responses_html = self.cleaned_data.get('responses', '').strip()
        return bleach.clean(responses_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

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
    ai_client = forms.ChoiceField(
        choices=API_CLIENT_CHOICES,
        label='Selecione a IA para Capturar',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    token = ModelChoiceField(
        queryset=UserToken.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Selecionar Token para Capturar',
        required=True
    )

    class Meta:
        model = TrainingCapture
        fields = ['token', 'ai_client']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário e define os tokens disponíveis conforme o usuário."""
        user = kwargs.pop('user', None)
        super(TrainingCaptureForm, self).__init__(*args, **kwargs)
        if user:
            tokens = UserToken.objects.filter(user=user)
            self.fields['token'].queryset = tokens
        else:
            self.fields['token'].queryset = UserToken.objects.none()
        
        if self.instance and self.instance.pk:
            self.initial['ai_client'] = self.instance.ai_client.api_client_class
            self.fields['token'].initial = self.instance.token

class AITrainingFileForm(forms.ModelForm):
    """Formulário para upload de arquivo de treinamento."""
    class Meta:
        model = AITrainingFile
        fields = ['name', 'file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_file(self):
        """Realiza a limpeza e validação do arquivo enviado.

        Returns:
            Arquivo validado.
        """
        file = self.cleaned_data.get('file')
        return file
    
class AIClientTrainingForm(forms.ModelForm):
    """Formulário para configuração de treinamento de um cliente de IA.

    Converte os parâmetros de treinamento para o formato 'key=value'.
    """
    training_parameters = forms.CharField(
        label='Parâmetros de Treinamento',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Exemplo:\nparam1=valor1\nparam2=valor2'
        }),
        help_text='Insira os parâmetros no formato chave=valor, uma por linha.',
        required=False
    )

    trained_model_name = forms.CharField(
        label='Nome do Modelo Treinado',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly',
        }),
    )

    class Meta:
        model = AIClientTraining
        fields = ['training_parameters']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário e converte o JSON para texto multiline."""
        super(AIClientTrainingForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.training_parameters:
            training_lines = [f"{key}={value}" for key, value in self.instance.training_parameters.items()]
            self.initial['training_parameters'] = "\n".join(training_lines)
        else:
            self.initial['training_parameters'] = ""
        self.fields['trained_model_name'].initial = self.instance.trained_model_name
        self.fields['trained_model_name'].widget.attrs['readonly'] = True

    def clean_trained_model_name(self):
        """Garante que o nome do modelo treinado não seja modificado.

        Returns:
            str: Nome do modelo treinado.
        """
        return self.initial.get('trained_model_name', self.instance.trained_model_name)

    def save(self, commit=True):
        """Salva o formulário garantido que o 'trained_model_name' permaneça inalterado."""
        self.instance.trained_model_name = self.initial.get('trained_model_name', self.instance.trained_model_name)
        return super().save(commit=commit)

    def clean_training_parameters(self):
        """Valida e converte os parâmetros de treinamento para um dicionário.

        Returns:
            dict: Configurações de treinamento.
        
        Raises:
            forms.ValidationError: Se alguma linha não estiver no formato válido.
        """
        configurations_text = self.cleaned_data.get('training_parameters', '').strip()
        configurations_dict = {}
        
        if configurations_text:
            for line_number, line in enumerate(configurations_text.splitlines(), start=1):
                if not line.strip():
                    continue
                if '=' not in line:
                    raise forms.ValidationError(f"Linha {line_number}: '{line}' não está no formato chave=valor.")
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if not key:
                    raise forms.ValidationError(f"Linha {line_number}: Chave vazia.")
                if not value:
                    raise forms.ValidationError(f"Linha {line_number}: Valor vazio para a chave '{key}'.")
                
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
                
                configurations_dict[key] = value
        
        return configurations_dict

class UserAITrainingFileForm(forms.ModelForm):
    """Formulário para upload de arquivo de treinamento vinculado ao usuário."""
    class Meta:
        model = AITrainingFile
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário, marcando o campo 'file' como obrigatório."""
        super(UserAITrainingFileForm, self).__init__(*args, **kwargs)
        self.fields['file'].required = True

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
            ai_clients: Lista de objetos com atributo 'name'.
        """
        ai_clients = kwargs.pop('ai_clients', [])
        super(TrainAIForm, self).__init__(*args, **kwargs)
        self.fields['ai_clients_to_train'].choices = [(client.name, client.name) for client in ai_clients]

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
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'cols': 100, 
            'rows': 20,
            'placeholder': 'Insira o prompt personalizado para este token.'
        }),
        required=False,
        help_text='Insira as respostas para todas as comparações.'
    )

    def clean_user_message(self):
        """Substitui '\\n' por quebras de linha reais no campo 'user_message'.

        Returns:
            str: Mensagem do usuário formatada.
        """
        user_message = self.cleaned_data.get('user_message', '')
        return user_message.replace('\\n', '\n')

    def clean_system_message(self):
        """Substitui '\\n' por quebras de linha reais no campo 'system_message'.

        Returns:
            str: Mensagem do sistema formatada.
        """
        system_message = self.cleaned_data.get('system_message', '')
        return system_message.replace('\\n', '\n')

    def clean_response(self):
        """Substitui '\\n' por quebras de linha reais no campo 'response'.

        Returns:
            str: Resposta formatada.
        """
        response = self.cleaned_data.get('response', '')
        return response.replace('\\n', '\n')

TrainingExampleFormSetFactory = formset_factory(
    TrainingExampleForm,
    formset=BaseTrainingExampleFormSet,
    can_delete=True,
    extra=0
)
