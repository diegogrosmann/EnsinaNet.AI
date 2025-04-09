// Configuração de AJAX para CSRF - usamos o csrftoken definido em utils.js

$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (csrftoken && !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});

// Função para realizar requisições AJAX de maneira padronizada
function ajaxAPI(url, method, data, options = {}) {
    const defaultOptions = {
        showLoading: true,
        processData: true,
        contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
        successMessage: null,
        errorMessage: 'Ocorreu um erro ao processar sua solicitação.'
    };
    
    const settings = { ...defaultOptions, ...options };
    
    const isFormData = data instanceof FormData;
    const isJsonContent = settings.contentType === 'application/json' || 
                         (options.headers && options.headers['Content-Type'] && 
                          options.headers['Content-Type'].includes('application/json'));
    
    // Trata o método HTTP para garantir que seja uma string válida
    let httpMethod = method.toUpperCase();
    const validMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'];
    if (!validMethods.includes(httpMethod)) {
        httpMethod = 'POST'; // Método mais seguro como fallback
    }
    
    // Configurar corretamente as opções para FormData ou JSON
    if (isFormData) {
        settings.processData = false;
        settings.contentType = false;
    } else if (isJsonContent && typeof data === 'object' && !(data instanceof String)) {
        // Se é JSON, converter o objeto para string JSON
        data = JSON.stringify(data);
        settings.contentType = 'application/json';
    }
    
    if (settings.showLoading) {
        showLoading();
    }
    
    return new Promise((resolve, reject) => {
        // Verificar a disponibilidade do servidor antes de enviar a requisição
        checkServerAvailability().then(isAvailable => {
            if (!isAvailable) {
                updateServerAvailabilityMessage(false);

                if (settings.showLoading) {
                    hideLoading();
                }
                
                resetRetry();
                checkAndRetry();
                const appError = APIResponse.create_failure({
                    message: 'Serviço indisponível',
                    status: 503,
                    responseJSON: null
                });
                reject(appError);
                return;
            }
            
            $.ajax({
                url: url,
                type: httpMethod,
                data: data,
                processData: settings.processData,
                contentType: settings.contentType,
                headers: options.headers || {},
                success: function(response) {
                    // Log dos dados retornados pelo servidor
                    console.log('URL da requisição:', url);
                    console.log('Método da requisição:', httpMethod);
                    console.log('Dados enviados:', data);
                    console.log('Resposta do servidor:', response);
                    
                    if (settings.showLoading) {
                        hideLoading();
                    }
                    
                    if (settings.successMessage) {
                        showMessage('success', settings.successMessage);
                    }
                    
                    let parsedResponse;
                    try {
                        parsedResponse = typeof response === 'string' ? JSON.parse(response) : response;
                        
                        // Converter o objeto JSON para uma instância de APIResponse
                        parsedResponse = APIResponse.from_json(parsedResponse);
                    } catch (e) {
                        console.warn('Erro ao fazer parse da resposta JSON:', e);
                        parsedResponse = APIResponse.create_failure('Erro ao processar resposta do servidor');
                    }
                    
                    resolve(parsedResponse);
                },
                error: function(xhr) {
                    if (settings.showLoading) {
                        hideLoading();
                    }
                    
                    let errorMsg = settings.errorMessage;
                    try {
                        const errorResponse = JSON.parse(xhr.responseText);
                        if (errorResponse && errorResponse.error && errorResponse.error.message) {
                            errorMsg = errorResponse.error.message;
                        }
                    } catch (e) {
                        console.error('Erro ao processar resposta de erro:', e);
                    }
                    
                    showMessage('error', errorMsg);
                    
                    const appError = APIResponse.create_failure({
                        message: errorMsg,
                        status: xhr.status,
                        responseJSON: null
                    });
                    
                    reject(appError);
                }
            });
        });
    });
}

// Classe para manipulação padronizada de respostas da API
class APIResponse {
    constructor(success, data = null, error = null) {
        this.success = success;
        this.data = data;
        this.error = error;
    }

    static create_success(data = null) {
        return new APIResponse(true, data, null);
    }

    static create_failure(error = null) {
        if (typeof error === 'string') {
            error = { message: error };
        }
        return new APIResponse(false, null, error);
    }

    static from_json(jsonData) {
        if (typeof jsonData === 'string') {
            try {
                jsonData = JSON.parse(jsonData);
            } catch (e) {
                return APIResponse.create_failure('Erro ao processar resposta do servidor');
            }
        }

        if (!jsonData) {
            return APIResponse.create_failure('Resposta vazia do servidor');
        }

        if (jsonData.success === true) {
            // Log detalhado dos dados recebidos
            console.debug("APIResponse construindo resposta de sucesso com dados:", jsonData.data);
            return APIResponse.create_success(jsonData.data);
        } else {
            return APIResponse.create_failure(jsonData.error || 'Erro desconhecido');
        }
    }

    showMessage(options = {}) {
        const defaultOptions = {
            showSuccess: true,
            successMessage: 'Operação realizada com sucesso',
            duration: 5000
        };
        
        const settings = { ...defaultOptions, ...options };
        
        if (this.success) {
            if (settings.showSuccess) {
                const message = this.data?.message || settings.successMessage;
                showMessage('success', message, settings.duration);
            }
        } else {
            const errorMsg = this.error?.message || 'Ocorreu um erro na operação';
            showMessage('error', errorMsg, settings.duration);
        }
        
        return this;
    }

    getData() {
        return this.data;
    }

    getError() {
        return this.error;
    }

    isSuccess() {
        return this.success;
    }
}

// Disponibiliza globalmente
window.APIResponse = APIResponse;
