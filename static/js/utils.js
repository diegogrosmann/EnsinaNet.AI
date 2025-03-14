/// <reference path="./types/global.d.ts" />

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

/**
 * Funções para gerenciar o loader da página
 */

// Controle do loader inicial da página
function showPageLoader() {
  const loader = document.getElementById('pageLoader');
  if (loader) {
    loader.style.display = 'flex';
    loader.style.opacity = '1';
  }
}

function hidePageLoader() {
  const loader = document.getElementById('pageLoader');
  if (loader) {
    loader.style.opacity = '0';
    setTimeout(() => {
      loader.style.display = 'none';
    }, 300);
  }
}

// Controle do loader de transição
function showTransitionLoader() {
  const transLoader = document.getElementById('transitionLoader');
  if (transLoader) {
    transLoader.style.display = 'flex';
  }
}

// Configura o loader de transição apenas para saída do site
function setupTransitionLoader() {
  // Removemos os eventos de cliques em links - eles não devem disparar o loader
  // O loader só será mostrado no evento beforeunload quando o usuário realmente sair da página
  
  // Para formulários, mantemos o comportamento mas melhoramos a detecção
  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    // Não aplicar a formulários com atributo data-no-loader ou que usam AJAX
    if (!form.hasAttribute('data-no-loader')) {
      form.addEventListener('submit', function(e) {
        // Verificamos se o formulário será enviado via AJAX
        const isAjaxForm = form.hasAttribute('data-ajax') || 
                          form.classList.contains('ajaxForm') || 
                          form.getAttribute('onsubmit')?.includes('ajax') ||
                          form.dataset.remote === 'true';
        
        // Só mostrar loader se for um envio tradicional, não AJAX
        if (!isAjaxForm && !e.defaultPrevented) {
          showTransitionLoader();
        }
      });
    }
  });
}

// Executar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
  // Esconde o loader quando o DOM terminar de carregar
  hidePageLoader();
  
  // Configura o loader de transição
  setupTransitionLoader();
});

// Garantir que o loader seja escondido quando todos os recursos carregarem
window.addEventListener('load', function() {
  hidePageLoader();
});

// Mostra o loader apenas quando o usuário realmente sai do site
window.addEventListener('beforeunload', function(e) {
  // Verificar se a navegação não é causada por um link interno ou AJAX
  // Se for uma saída real do site, mostrar o loader
  if (!e.defaultPrevented) {
    showPageLoader();
  }
});

// Inicializa o loader ao carregar o script
showPageLoader();

// Inicializações gerais
document.addEventListener('DOMContentLoaded', function() {
    initToasts();
    initThemeDetection();
});
