// Função de mensagens/toasts com ícone
// Removendo a duplicação das funções showMessage, showLoading e hideLoading
// Elas já estão definidas em utils.js

function closeMessage(toastId) {
    const toast = document.getElementById(toastId);
    if (toast) {
        const bsToast = bootstrap.Toast.getInstance(toast);
        if (bsToast) {
            bsToast.hide();
        }
    }
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

// Funções para gerenciar carregamento de páginas
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

function showTransitionLoader() {
  const transLoader = document.getElementById('transitionLoader');
  if (transLoader) {
    transLoader.style.display = 'flex';
  }
}

function hideTransitionLoader() {
  const transLoader = document.getElementById('transitionLoader');
  if (transLoader) {
    transLoader.style.display = 'none';
  }
}

function setupTransitionLoader() {
  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    if (!form.hasAttribute('data-no-loader')) {
      form.addEventListener('submit', function(e) {
        const isAjaxForm = form.hasAttribute('data-ajax') || 
                          form.classList.contains('ajaxForm') || 
                          form.getAttribute('onsubmit')?.includes('ajax') ||
                          form.dataset.remote === 'true';
        const formAction = form.getAttribute('action') || '';
        const isNoLoader = formAction.includes('no_loader=true');
        if (!isAjaxForm && !isNoLoader && !e.defaultPrevented) {
          showTransitionLoader();
        }
      });
    }
  });
}

// Modifique a inicialização para evitar conflitos
document.addEventListener('DOMContentLoaded', function() {
  // Certifique-se que as funções de página e transição são inicializadas
  hidePageLoader();
  hideTransitionLoader();
  setupTransitionLoader();
  initToasts();
});

// Remova a chamada para initServerAvailabilityCheck aqui - deixe apenas em utils.js
window.addEventListener('load', function() {
  hidePageLoader();
  hideTransitionLoader();
});

// Remova a chamada duplicada para initServerAvailabilityCheck
window.addEventListener('pageshow', function(event) {
  if (event.persisted) {
    hidePageLoader();
    hideTransitionLoader();
  }
});

window.addEventListener('beforeunload', function(e) {
  if (window.location.href.includes('no_loader=true')) {
    e.preventDefault();
    return;
  }
  
  if (!e.defaultPrevented) {
    showTransitionLoader();
  }
});

// Show loader initially
showPageLoader();
