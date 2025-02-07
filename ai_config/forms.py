import json
import bleach
from django import forms
from django.forms import formset_factory, BaseFormSet, ModelChoiceField
from django.contrib.auth import get_user_model
from tinymce.widgets import TinyMCE

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media = forms.Media()
        for form in self.forms:
            self.media += form.media

class AIClientGlobalConfigForm(forms.ModelForm):
    """
    Formulário para criar/editar AIClientGlobalConfiguration.
    Adicionamos:
     - 'name' para nomear o cliente
     - 'api_url' como campo opcional
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
        super(AIClientGlobalConfigForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.api_key:
            masked_key = self.mask_api_key(self.instance.api_key)
            self.initial['api_key'] = masked_key
            self.initial['original_api_key'] = self.instance.api_key

    def mask_api_key(self, api_key):
        if len(api_key) > 8:
            return f"{api_key[:4]}****{api_key[-4:]}"
        else:
            return '*' * len(api_key)

    def clean_api_key(self):
        api_key = self.cleaned_data.get('api_key')
        original_api_key = self.initial.get('original_api_key')
        masked_key = self.mask_api_key(original_api_key) if original_api_key else ''
        
        if api_key == masked_key:
            return original_api_key
        else:
            return api_key

class AIClientConfigurationForm(forms.ModelForm):
    """
    Formulário para AIClientConfiguration,
    com o campo 'configurations' em formato chave=valor, um por linha.
    """

    # Campo de texto onde o usuário digita as configurações como "key=value" multiline
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
        fields = ['name', 'ai_client', 'enabled', 'model_name', 'configurations']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """
        Se já houver algo salvo no JSONField configurations,
        convertemos de dict -> multiline 'key=value'.
        Se for vazio ou None, deixamos o campo em branco.
        """
        if self.instance and self.instance.configurations:
            # Se for um dict e tiver pelo menos 1 item, convertemos
            if isinstance(self.instance.configurations, dict) and len(self.instance.configurations) > 0:
                lines = []
                for k, v in self.instance.configurations.items():
                    lines.append(f"{k}={v}")
                self.initial['configurations'] = "\n".join(lines)
            else:
                # Se for um dict vazio ou qualquer outra coisa "falsa", deixa vazio
                self.initial['configurations'] = ""
        else:
            # Se não existir ou for None, também deixamos vazio
            self.initial['configurations'] = ""

    def clean_name(self):
        """
        Exemplo simples para garantir que 'name' não esteja vazio
        ou tenha espaços em excesso.
        """
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Nome não pode ser vazio.")
        return name

    def clean_configurations(self):
        """
        Converte o texto multiline (key=value) em dicionário:
          - cada linha deve ter formato chave=valor
          - ignora linhas vazias
          - converte int/float sempre que possível
        """
        data = self.cleaned_data.get('configurations', '').strip()
        config_dict = {}

        if data:
            for line_number, line in enumerate(data.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue  # ignora linha vazia
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

                # Tenta converter para int ou float
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass  # Mantém string caso não seja número

                config_dict[key] = value

        return config_dict
    
class TokenAIConfigurationForm(forms.ModelForm):
    base_instruction = forms.CharField(
        label='Instrução Base',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'cols': 100, 
            'rows': 20,
            'placeholder': 'Insira a instrução base personalizada para este token.'
        }),
        required=False,
        help_text='Insira a instrução base personalizada para este token.'
    )
    prompt = forms.CharField(
        label='Prompt',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'cols': 100, 
            'rows': 20,
            'placeholder': 'Insira o prompt personalizado para este token.'
        }),
        required=False,
        help_text='Insira o prompt para todas as comparações.'
    )
    responses = forms.CharField(
        label='Respostas',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'cols': 100, 
            'rows': 20,
            'placeholder': 'Insira o prompt personalizado para este token.'
        }),
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
        user = kwargs.pop('user', None)
        super(TokenAIConfigurationForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['training_file'].queryset = AITrainingFile.objects.filter(user=user)
        self.user = user

    def clean_base_instruction(self):
        base_instruction_html = self.cleaned_data.get('base_instruction', '').strip()
        return bleach.clean(base_instruction_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_prompt(self):
        prompt_html = self.cleaned_data.get('prompt', '').strip()
        return bleach.clean(prompt_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_responses(self):
        responses_html = self.cleaned_data.get('responses', '').strip()
        return bleach.clean(responses_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

class AITrainingFileNameForm(forms.Form):
    name = forms.CharField(
        label='Nome do Arquivo de Treinamento',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Insira um nome para identificar facilmente este arquivo de treinamento.'
    )

class TrainingCaptureForm(forms.ModelForm):
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
        user = kwargs.pop('user', None)
        super(TrainingCaptureForm, self).__init__(*args, **kwargs)
        if user:
            tokens = UserToken.objects.filter(user=user)
            self.fields['token'].queryset = tokens
        else:
            self.fields['token'].queryset = UserToken.objects.none()
        
        # Definir valores iniciais
        if self.instance and self.instance.pk:
            self.initial['ai_client'] = self.instance.ai_client.api_client_class
            self.fields['token'].initial = self.instance.token

class AITrainingFileForm(forms.ModelForm):
    class Meta:
        model = AITrainingFile
        fields = ['name', 'file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        return file
    
class AIClientTrainingForm(forms.ModelForm):
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
        super(AIClientTrainingForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.training_parameters:
            training_lines = [f"{key}={value}" for key, value in self.instance.training_parameters.items()]
            self.initial['training_parameters'] = "\n".join(training_lines)
        else:
            self.initial['training_parameters'] = ""

        # Inicializa o campo 'trained_model_name' com o valor do modelo treinado
        self.fields['trained_model_name'].initial = self.instance.trained_model_name
        self.fields['trained_model_name'].widget.attrs['readonly'] = True

    def clean_trained_model_name(self):
        # Retorna o valor inicial para garantir que não seja modificado
        return self.initial.get('trained_model_name', self.instance.trained_model_name)

    def save(self, commit=True):
        # Garante que 'trained_model_name' não seja alterado
        self.instance.trained_model_name = self.initial.get('trained_model_name', self.instance.trained_model_name)
        return super().save(commit=commit)

    def clean_training_parameters(self):
        configurations_text = self.cleaned_data.get('training_parameters', '').strip()
        configurations_dict = {}
        
        if configurations_text:
            for line_number, line in enumerate(configurations_text.splitlines(), start=1):
                if not line.strip():
                    continue  # Ignora linhas vazias
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
                    pass  # Mantém como string se não for numérico
                
                configurations_dict[key] = value
        
        return configurations_dict

class UserAITrainingFileForm(forms.ModelForm):
    class Meta:
        model = AITrainingFile
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserAITrainingFileForm, self).__init__(*args, **kwargs)
        self.fields['file'].required = True

class TrainAIForm(forms.Form):
    ai_clients_to_train = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        label='Selecionar IAs para Treinar',
        required=True,
        help_text='Selecione as IAs que deseja treinar.',
    )

    def __init__(self, *args, **kwargs):
        ai_clients = kwargs.pop('ai_clients', [])
        super(TrainAIForm, self).__init__(*args, **kwargs)
        self.fields['ai_clients_to_train'].choices = [(client.name, client.name) for client in ai_clients]

class TrainingExampleForm(forms.Form):
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
        user_message = self.cleaned_data.get('user_message', '')
        user_message = user_message.replace('\\n', '\n')
        return user_message

    def clean_system_message(self):
        system_message = self.cleaned_data.get('system_message', '')
        system_message = system_message.replace('\\n', '\n')
        return system_message

    def clean_response(self):
        response = self.cleaned_data.get('response', '')
        response = response.replace('\\n', '\n')
        return response

TrainingExampleFormSetFactory = formset_factory(
    TrainingExampleForm,
    formset=BaseTrainingExampleFormSet,
    can_delete=True,
    extra=0
)
