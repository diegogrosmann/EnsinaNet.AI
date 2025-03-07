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

// Função utilitária para mostrar mensagens toast
function showMessage(type, message) {
    const toast = $('<div>').addClass('toast').addClass(`bg-${type}`).attr('role', 'alert')
        .append($('<div>').addClass('toast-body').text(message));
    
    $('#toast-container').append(toast);
    toast.toast({delay: 3000}).toast('show');
    
    toast.on('hidden.bs.toast', function() {
        $(this).remove();
    });
}

// Função para formatar datas
function formatDate(date) {
    return new Date(date).toLocaleDateString('pt-BR');
}

// Inicializações globais quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Inicializa todos os tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();

    // Inicializa todos os popovers
    $('[data-bs-toggle="popover"]').popover();
    
    // Adiciona handlers para modais
    $('.modal').on('show.bs.modal', function() {
        document.body.style.overflow = 'hidden';
    });
    
    $('.modal').on('hidden.bs.modal', function() {
        document.body.style.overflow = '';
    });
});

function buildUrl(url, tempID, replaceID) {
    return url.replace(tempID, replaceID);
}

// Sistema unificado de mensagens/toasts
function showMessage(type, message, duration = 5000) {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) return;
    
    // Definir classes e ícones com base no tipo
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

// Gerenciamento de indicador de carregamento AJAX
function showAjaxLoading() {
    document.querySelector('.ajax-loading').style.display = 'flex';
}

function hideAjaxLoading() {
    document.querySelector('.ajax-loading').style.display = 'none';
}

// Interceptar solicitações AJAX para mostrar indicador de carregamento
(function() {
    const originalFetch = window.fetch;
    window.fetch = function() {
        showAjaxLoading();
        return originalFetch.apply(this, arguments).finally(hideAjaxLoading);
    };
    
    const originalXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function() {
        this.addEventListener('loadstart', showAjaxLoading);
        this.addEventListener('loadend', hideAjaxLoading);
        originalXHROpen.apply(this, arguments);
    };
})();

// Controle de mudanças não salvas
window.hasUnsavedChanges = false;
window.addEventListener('beforeunload', function(e) {
    if (window.hasUnsavedChanges) {
        e.preventDefault();
        e.preventDefault();
        return 'Você tem alterações não salvas. Deseja realmente sair?';
    }
});