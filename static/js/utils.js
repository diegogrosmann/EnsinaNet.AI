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

// Configurar CSRF token para todas requisições AJAX
const csrftoken = getCookie('csrftoken');

$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});

// Função de mensagens/toasts com ícone
function showMessage(type, message, duration = 5000) {
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
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center border-0 ${bgClass}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.setAttribute('data-bs-delay', duration);
    
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
    
    // Guardar o texto original
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    
    // Adicionar spinner e texto
    button.innerHTML = `
        <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        <span class="ms-1">${loadingText}</span>
    `;
}

function hideButtonLoading(button) {
    if (!button || !button.dataset.originalHtml) return;
    
    // Restaurar o estado original
    button.innerHTML = button.dataset.originalHtml;
    button.disabled = false;
    delete button.dataset.originalHtml;
}

// Controle de mudanças não salvas
window.hasUnsavedChanges = false;
window.addEventListener('beforeunload', function(e) {
    if (window.hasUnsavedChanges) {
        e.preventDefault();
        e.preventDefault();
        return 'Você tem alterações não salvas. Deseja realmente sair?';
    }
});

// Sistema de detecção e gerenciamento de tema
function initThemeDetection() {
    // Inicialização do sistema de temas (se disponível)
    if (typeof initThemeSystem === 'function') {
        // O novo sistema de temas irá gerenciar tudo
        initThemeSystem();
    }
}

// Alternar tema manualmente - função legada, mantida apenas para compatibilidade
function toggleTheme() {
    // Se o novo sistema de temas estiver disponível, use-o
    if (typeof toggleThemeMode === 'function') {
        toggleThemeMode();
    }
}

function buildUrl(url, tempID, replaceID) {
    return url.replace(tempID, replaceID);
}

// Funções do MarkdownX são delegadas para o arquivo markdownx.js
// Aliases para manter compatibilidade com código existente
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

// Inicializações gerais
document.addEventListener('DOMContentLoaded', function() {
    initToasts();
    initThemeDetection();
});
