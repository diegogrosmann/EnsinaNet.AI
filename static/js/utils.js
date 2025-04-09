// Funções básicas e utilitárias usadas por todo o sistema

// Configuração de AJAX para CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Declaramos esta variável globalmente para uso em outros arquivos
const csrftoken = getCookie('csrftoken');

// Variáveis e funções utilitárias gerais
window.hasUnsavedChanges = false;
window.addEventListener('beforeunload', function(e) {
    if (window.hasUnsavedChanges) {
        e.preventDefault();
        return 'Você tem alterações não salvas. Deseja realmente sair?';
    }
});

function initThemeDetection() {
    if (typeof initThemeSystem === 'function') {
        initThemeSystem();
    }
}

function toggleTheme() {
    if (typeof toggleThemeMode === 'function') {
        toggleThemeMode();
    }
}

function buildUrl(url, tempID, replaceID) {
    if (!url || !tempID || replaceID === undefined) {
        console.error('buildUrl: parâmetros inválidos', {url, tempID, replaceID});
        return url;
    }
    return url.replace(tempID, replaceID);
}

function initMarkdownX() {
    if (typeof MarkdownX !== 'undefined') {
        MarkdownX.init();
    } else {
        console.warn('MarkdownX não está disponível');
    }
}

function setupMarkdownResizers() {
    if (typeof MarkdownX !== 'undefined') {
        MarkdownX.setupResizers();
    }
}

function resetMarkdownHeight() {
    if (typeof MarkdownX !== 'undefined') {
        MarkdownX.resetHeight();
    }
}

// IMPORTANTE: Remover qualquer declaração de APIResponse e ModelRegistry deste arquivo
// Essas classes agora estão em api.js e models.js respectivamente

document.addEventListener('DOMContentLoaded', function() {
    initThemeDetection();
});

// Função de mensagens/toasts com ícone
function showMessage(type, message, duration = 5000, autoClose = true) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;
    
    let bgClass, iconClass;
    switch(type) {
        case 'success':
            bgClass = 'text-bg-success';
            iconClass = 'bi-check-circle';
            break;
        case 'error':
            bgClass = 'text-bg-danger';
            iconClass = 'bi-exclamation-circle';
            break;
        case 'warning':
            bgClass = 'text-bg-warning';
            iconClass = 'bi-exclamation-triangle';
            break;
        default:
            bgClass = 'text-bg-info';
            iconClass = 'bi-info-circle';
    }
    
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center border-0 ${bgClass}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    if (autoClose) {
        toast.setAttribute('data-bs-delay', duration);
    } else {
        toast.setAttribute('data-bs-autohide', 'false');
    }
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi ${iconClass} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    
    return toastId;
}

function closeMessage(toastId) {
    const toast = document.getElementById(toastId);
    if (toast) {
        const bsToast = bootstrap.Toast.getInstance(toast);
        if (bsToast) {
            bsToast.hide();
        }
    }
}

// Inicializa todos os toasts estáticos na página
function initToasts() {
    const toastElList = document.querySelectorAll('.toast');
    toastElList.forEach(function(toastEl) {
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    });
}

// Gerenciamento de indicador de carregamento AJAX
function showLoading() {
    document.querySelector('.ajax-loading').style.display = 'flex';
}

function hideLoading() {
    document.querySelector('.ajax-loading').style.display = 'none';
}

// Funções utilitárias para indicadores de carregamento em botões
function showButtonLoading(button, loadingText = 'Carregando...') {
    if (!button) return;
    
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    
    button.innerHTML = `
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span class="ms-1">${loadingText}</span>
    `;
}

function hideButtonLoading(button) {
    if (!button || !button.dataset.originalHtml) return;
    
    button.innerHTML = button.dataset.originalHtml;
    button.disabled = false;
    delete button.dataset.originalHtml;
}

window.addEventListener('beforeunload', function(e) {
    if (window.location.href.includes('no_loader=true')) {
        e.preventDefault();
        return;
    }
    
    if (!e.defaultPrevented) {
        showTransitionLoader();
    }
});

showPageLoader();

document.addEventListener('DOMContentLoaded', function() {
    initToasts();
    initThemeDetection();
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
}

let retryCount = 0;
let retryInterval = 5; // segundos
let maxRetryInterval = 60; // segundos
let countdownIntervalId = null; // Para rastrear o intervalo do contador

// Função para verificar a disponibilidade do servidor
function checkServerAvailability() {
    return new Promise((resolve) => {
        $.ajax({
            url: '/api/healthcheck/', // Endpoint para verificar a saúde do servidor
            type: 'GET',
            timeout: 5000, // Tempo limite de 5 segundos
            success: function() {
                resolve(true); // Servidor disponível
                resetRetry();
            },
            error: function() {
                resolve(false); // Servidor indisponível
            }
        });
    });
}

// Função para exibir/ocultar a mensagem de servidor indisponível
function updateServerAvailabilityMessage(isAvailable) {
    const messageElement = document.getElementById('server-unavailable-message');
    if (messageElement) {
        messageElement.style.display = isAvailable ? 'none' : 'block';
    }
}

// Função para atualizar o contador regressivo
function updateCountdown(seconds) {
    const countdownElement = document.getElementById('retry-countdown');
    if (countdownElement) {
        countdownElement.textContent = ` (Tentando novamente em ${seconds}s)`;
    }
}

// Função para resetar o contador de tentativas
function resetRetry() {
    retryCount = 0;
    retryInterval = 5;
    
    // Limpar qualquer intervalo existente
    if (countdownIntervalId) {
        clearInterval(countdownIntervalId);
        countdownIntervalId = null;
    }
}

// Função para tentar novamente a verificação de disponibilidade
async function retryServerAvailability() {
    // Limpar qualquer intervalo existente antes de iniciar um novo
    if (countdownIntervalId) {
        clearInterval(countdownIntervalId);
        countdownIntervalId = null;
    }
    
    updateServerAvailabilityMessage(false);
    
    let seconds = retryInterval;
    updateCountdown(seconds);
    
    countdownIntervalId = setInterval(() => {
        seconds--;
        updateCountdown(seconds);
        
        if (seconds <= 0) {
            clearInterval(countdownIntervalId);
            countdownIntervalId = null;
            checkAndRetry();
        }
    }, 1000);
}

// Função para verificar e tentar novamente
async function checkAndRetry() {
    const isAvailable = await checkServerAvailability();
    if (isAvailable) {
        updateServerAvailabilityMessage(true);
    } else {
        retryCount++;
        retryInterval = Math.min(retryInterval * 2, maxRetryInterval);
        retryServerAvailability();
    }
}

// Inicializar a verificação de disponibilidade do servidor
async function initServerAvailabilityCheck() {
    console.log("Iniciando verificação de disponibilidade do servidor");
    const isAvailable = await checkServerAvailability();
    console.log("Servidor disponível:", isAvailable);

    if (!isAvailable) {
        console.log("Servidor indisponível, iniciando contador");
        // Certifique-se que a mensagem é exibida e o contador inicia
        updateServerAvailabilityMessage(false);
        retryServerAvailability(); // Isso iniciará o contador automaticamente
    } else {
        console.log("Servidor disponível, ocultando mensagem");
        updateServerAvailabilityMessage(true);
    }
}

// Certifique-se de que a verificação de disponibilidade do servidor é iniciada somente uma vez
let serverAvailabilityCheckInitialized = false;

document.addEventListener('DOMContentLoaded', function() {
    initThemeDetection();
    
    if (!serverAvailabilityCheckInitialized) {
        serverAvailabilityCheckInitialized = true;
        initServerAvailabilityCheck();
        console.log("Verificação de disponibilidade do servidor inicializada");
    }

    // Adicionar evento de clique ao botão de tentar novamente
    const retryButton = document.getElementById('retry-button');
    if (retryButton) {
        retryButton.addEventListener('click', function() {
            resetRetry();
            checkAndRetry();
        });
    }
});
