/**
 * Utilitários para o componente MarkdownX
 * Este arquivo contém funções específicas para manipulação do editor markdown
 */

// Namespace para funções do MarkdownX
const MarkdownX = {
    // Flag para controle de redimensionamento
    isResizing: false,
    
    // Prevenção de auto-salvamento
    preventAutoSubmit: true,

    /**
     * Inicializa todos os componentes MarkdownX na página
     */
    init: function() {
        // Aguardar um momento para garantir que o markdownx esteja carregado
        setTimeout(() => {
            this.setupResizers();
            this.resetHeight();
            this.setupChangeTracking();
        }, 100);
    },

    /**
     * Configura os redimensionadores para todos os editores markdownx
     */
    setupResizers: function() {
        document.querySelectorAll('.markdownx').forEach(markdownArea => {
            const editor = markdownArea.querySelector('.markdownx-editor');
            const preview = markdownArea.querySelector('.markdownx-preview');
            
            if (!editor || !preview) return;
            
            // Evitar adicionar redimensionadores duplicados
            if (markdownArea.querySelector('.markdownx-resizer')) return;
            
            // Criar o elemento resizer
            const resizer = document.createElement('div');
            resizer.className = 'markdownx-resizer';
            markdownArea.appendChild(resizer);
            
            // Configurar os eventos de redimensionamento
            resizer.addEventListener('mousedown', function(e) {
                e.preventDefault();
                
                const startY = e.clientY;
                const startHeight = parseInt(window.getComputedStyle(editor).height);
                
                // Marcar que estamos redimensionando
                MarkdownX.isResizing = true;
                
                document.addEventListener('mousemove', resize);
                document.addEventListener('mouseup', stopResize);
                
                function resize(e) {
                    const newHeight = startHeight + e.clientY - startY;
                    if (newHeight >= 150) { // Respeitar a altura mínima
                        editor.style.height = `${newHeight}px`;
                        preview.style.height = `${newHeight}px`;
                    }
                }
                
                function stopResize() {
                    document.removeEventListener('mousemove', resize);
                    document.removeEventListener('mouseup', stopResize);
                    MarkdownX.isResizing = false;
                }
            });
        });
    },

    /**
     * Restaura a altura correta do markdownx e neutraliza estilos do Bootswatch no preview
     */
    resetHeight: function() {
        document.querySelectorAll('.markdownx-editor, .markdownx-preview').forEach(element => {
            // Forçar a altura definida no CSS
            element.style.height = '300px';
            
            // Remover quaisquer atributos de estilo inline que possam afetar a altura
            element.style.removeProperty('min-height');
            element.style.removeProperty('max-height');
            
            // Adicionar classe específica para o preview que vai neutralizar os estilos do Bootswatch
            if (element.classList.contains('markdownx-preview')) {
                element.classList.add('markdown-neutral-style');
            }
        });
        
        // Observar mudanças no DOM para manter a altura correta
        this.observeStyling();
    },

    /**
     * Configura um MutationObserver para manter os estilos do markdownx consistentes
     */
    observeStyling: function() {
        if (typeof MutationObserver === 'undefined') return;
        
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    const target = mutation.target;
                    if (target.classList.contains('markdownx-editor') || target.classList.contains('markdownx-preview')) {
                        // Se a altura foi alterada e não foi pelo nosso resizer, restaure-a
                        if (target.style.height !== '300px' && !MarkdownX.isResizing) {
                            target.style.height = '300px';
                        }
                    }
                }
            });
        });
        
        // Observar alterações de estilo em todos os elementos markdownx
        document.querySelectorAll('.markdownx').forEach(container => {
            observer.observe(container, { 
                subtree: true,
                attributes: true,
                attributeFilter: ['style']
            });
        });
    },

    /**
     * Configura o rastreamento de mudanças para o editor markdownx
     * usando o sistema de controle de mudanças do utils.js
     */
    setupChangeTracking: function() {
        // Monitora mudanças nos editores markdown
        document.querySelectorAll('.markdownx-editor').forEach(editor => {
            const originalContent = editor.value;
            
            // Eventos que podem alterar o conteúdo
            const events = ['input', 'change', 'paste', 'keyup'];
            
            events.forEach(eventType => {
                editor.addEventListener(eventType, () => {
                    // Se o conteúdo mudou, marca que há mudanças não salvas
                    if (editor.value !== originalContent) {
                        window.hasUnsavedChanges = true;
                        
                        // Opcional: adiciona indicador visual
                        const form = editor.closest('form');
                        if (form) {
                            const submitBtn = form.querySelector('button[type="submit"]');
                            if (submitBtn && !submitBtn.classList.contains('btn-warning')) {
                                submitBtn.classList.add('btn-unsaved');
                                
                                // Efeito visual para indicar mudanças não salvas
                                if (!submitBtn.querySelector('.unsaved-indicator')) {
                                    const indicator = document.createElement('span');
                                    indicator.className = 'unsaved-indicator ms-1';
                                    indicator.innerHTML = '•';
                                    submitBtn.appendChild(indicator);
                                }
                            }
                        }
                    }
                });
            });
            
            // Limpa o indicador quando o formulário é submetido
            const form = editor.closest('form');
            if (form) {
                form.addEventListener('submit', () => {
                    window.hasUnsavedChanges = false;
                    
                    const submitBtn = form.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        submitBtn.classList.remove('btn-unsaved');
                        const indicator = submitBtn.querySelector('.unsaved-indicator');
                        if (indicator) indicator.remove();
                    }
                });
            }
        });
        
        // Captura submissões AJAX bem-sucedidas
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            return originalFetch.apply(this, args).then(response => {
                if (response.ok && args[0].includes('prompt_config')) {
                    window.hasUnsavedChanges = false;
                    
                    // Remove indicadores visuais após salvamento bem-sucedido
                    document.querySelectorAll('.btn-unsaved').forEach(btn => {
                        btn.classList.remove('btn-unsaved');
                        const indicator = btn.querySelector('.unsaved-indicator');
                        if (indicator) indicator.remove();
                    });
                }
                return response;
            });
        };
    }
};

// Inicializar quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar MarkdownX se estiver presente na página
    if (document.querySelector('.markdownx')) {
        MarkdownX.init();
    }
});
