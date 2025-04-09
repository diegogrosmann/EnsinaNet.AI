/**
 * Gerenciador de temas Bootswatch
 * Este arquivo contém a lista completa de temas Bootswatch disponíveis
 * e funcionalidades para gerenciá-los.
 */

// Lista completa dos temas Bootswatch
const BOOTSWATCH_THEMES = {
    // Tema padrão (Bootstrap)
    "default": {
        name: "Padrão",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
    },
    // Temas claros
    "cerulean": {
        name: "Cerulean",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/cerulean/bootstrap.min.css"
    },
    "cosmo": {
        name: "Cosmo",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/cosmo/bootstrap.min.css"
    },
    "flatly": {
        name: "Flatly",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/flatly/bootstrap.min.css"
    },
    "journal": {
        name: "Journal",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/journal/bootstrap.min.css"
    },
    "litera": {
        name: "Litera",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/litera/bootstrap.min.css"
    },
    "lumen": {
        name: "Lumen",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/lumen/bootstrap.min.css"
    },
    "lux": {
        name: "Lux",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/lux/bootstrap.min.css"
    },
    "materia": {
        name: "Materia",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/materia/bootstrap.min.css"
    },
    "minty": {
        name: "Minty",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/minty/bootstrap.min.css"
    },
    "morph": {
        name: "Morph",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/morph/bootstrap.min.css"
    },
    "pulse": {
        name: "Pulse",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/pulse/bootstrap.min.css"
    },
    "sandstone": {
        name: "Sandstone",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/sandstone/bootstrap.min.css"
    },
    "simplex": {
        name: "Simplex",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/simplex/bootstrap.min.css"
    },
    "spacelab": {
        name: "Spacelab",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/spacelab/bootstrap.min.css"
    },
    "united": {
        name: "United",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/united/bootstrap.min.css"
    },
    "yeti": {
        name: "Yeti",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/yeti/bootstrap.min.css"
    },
    "zephyr": {
        name: "Zephyr",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/zephyr/bootstrap.min.css"
    },
    
    // Temas escuros
    "cyborg": {
        name: "Cyborg",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/cyborg/bootstrap.min.css"
    },
    "darkly": {
        name: "Darkly",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/darkly/bootstrap.min.css"
    },
    "quartz": {
        name: "Quartz",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/quartz/bootstrap.min.css"
    },
    "slate": {
        name: "Slate",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/slate/bootstrap.min.css"
    },
    "solar": {
        name: "Solar",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/solar/bootstrap.min.css"
    },
    "superhero": {
        name: "Superhero",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/superhero/bootstrap.min.css"
    },
    "vapor": {
        name: "Vapor",
        isDark: true,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/vapor/bootstrap.min.css"
    },
    "sketchy": {
        name: "Sketchy",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootswatch@5.3.0/dist/sketchy/bootstrap.min.css"
    }
};

// Configuração padrão do sistema de temas
const DEFAULT_THEME_CONFIG = {
    lightTheme: "default",    // Tema claro padrão (Bootstrap)
    darkTheme: "superhero", // Tema escuro padrão
    themeStorageKey: "theme",
    themeModeStorageKey: "themeMode" // 'light' ou 'dark'
};

/**
 * Retorna a lista completa de temas
 * @returns {Object} Lista de temas Bootswatch
 */
function getAllThemes() {
    return BOOTSWATCH_THEMES;
}

/**
 * Retorna a lista de temas claros
 * @returns {Object} Lista de temas claros
 */
function getLightThemes() {
    return Object.fromEntries(
        Object.entries(BOOTSWATCH_THEMES)
            .filter(([_, theme]) => !theme.isDark)
    );
}

/**
 * Retorna a lista de temas escuros
 * @returns {Object} Lista de temas escuros
 */
function getDarkThemes() {
    return Object.fromEntries(
        Object.entries(BOOTSWATCH_THEMES)
            .filter(([_, theme]) => theme.isDark)
    );
}

/**
 * Troca para um tema específico pelo ID
 * @param {string} themeId - ID do tema
 * @returns {boolean} Sucesso da troca
 */
function switchToTheme(themeId) {
    if (!BOOTSWATCH_THEMES[themeId]) {
        console.error(`Tema "${themeId}" não encontrado`);
        return false;
    }
    
    const theme = BOOTSWATCH_THEMES[themeId];
    const themeLink = document.getElementById('themeLink');
    
    if (!themeLink) {
        console.error('Elemento de tema não encontrado no DOM');
        return false;
    }
    
    themeLink.href = theme.url;
    
    // Salvar preferência
    const mode = theme.isDark ? 'dark' : 'light';
    localStorage.setItem(DEFAULT_THEME_CONFIG.themeModeStorageKey, mode);
    localStorage.setItem(DEFAULT_THEME_CONFIG.themeStorageKey, themeId);
    
    // Atualizar a classe dark-theme no documento
    if (theme.isDark) {
        document.documentElement.classList.add('dark-theme');
        if (document.getElementById('theme-toggle')) {
            document.getElementById('theme-toggle').checked = true;
        }
    } else {
        document.documentElement.classList.remove('dark-theme');
        if (document.getElementById('theme-toggle')) {
            document.getElementById('theme-toggle').checked = false;
        }
    }
    
    return true;
}

/**
 * Alterna entre o modo claro e escuro usando os temas padrão configurados
 */
function toggleThemeMode() {
    const isDarkMode = document.documentElement.classList.contains('dark-theme');
    const savedLightTheme = localStorage.getItem('lightThemeId') || DEFAULT_THEME_CONFIG.lightTheme;
    const savedDarkTheme = localStorage.getItem('darkThemeId') || DEFAULT_THEME_CONFIG.darkTheme;
    
    if (isDarkMode) {
        // Mudar para o tema claro
        switchToTheme(savedLightTheme);
    } else {
        // Mudar para o tema escuro
        switchToTheme(savedDarkTheme);
    }
}

/**
 * Inicializa o sistema de temas
 */
function initThemeSystem() {
    // Criar elemento de link para o tema (ou usar o existente)
    let themeLink = document.getElementById('themeLink');
    if (!themeLink) {
        themeLink = document.createElement('link');
        themeLink.id = 'themeLink';
        themeLink.rel = 'stylesheet';
        document.head.appendChild(themeLink);
    }
    
    // Configurar tema inicial com base nas preferências
    const savedTheme = localStorage.getItem(DEFAULT_THEME_CONFIG.themeStorageKey);
    const savedMode = localStorage.getItem(DEFAULT_THEME_CONFIG.themeModeStorageKey);
    const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Determinar o tema inicial
    let initialTheme;
    
    if (savedTheme && BOOTSWATCH_THEMES[savedTheme]) {
        // Se temos um tema salvo específico, usá-lo
        initialTheme = savedTheme;
    } else if (savedMode) {
        // Se temos um modo salvo, usar o tema padrão para esse modo
        initialTheme = savedMode === 'dark' 
            ? DEFAULT_THEME_CONFIG.darkTheme 
            : DEFAULT_THEME_CONFIG.lightTheme;
    } else {
        // Caso contrário, detectar com base na preferência do sistema
        initialTheme = prefersDarkMode 
            ? DEFAULT_THEME_CONFIG.darkTheme 
            : DEFAULT_THEME_CONFIG.lightTheme;
    }
    
    // Aplicar o tema inicial
    switchToTheme(initialTheme);
    
    // Configurar evento para mudança nas preferências do sistema
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        // Só mudar automaticamente se o usuário não tiver uma preferência salva
        if (!savedTheme && !savedMode) {
            const newTheme = e.matches 
                ? DEFAULT_THEME_CONFIG.darkTheme 
                : DEFAULT_THEME_CONFIG.lightTheme;
            switchToTheme(newTheme);
        }
    });
    
    // Preencher o seletor de temas
    populateThemeSelector();
}

/**
 * Preenche o seletor de temas no menu
 */
function populateThemeSelector() {
    const themeSelector = document.getElementById('themeSelector');
    if (!themeSelector) return;
    
    // Limpar conteúdo atual
    themeSelector.innerHTML = '';
    
    // Adicionar cabeçalhos e temas
    
    // Seção de temas claros
    const lightThemes = getLightThemes();
    const lightHeader = document.createElement('li');
    lightHeader.innerHTML = '<h6 class="dropdown-header">Temas Claros</h6>';
    themeSelector.appendChild(lightHeader);
    
    Object.entries(lightThemes).forEach(([id, theme]) => {
        const item = createThemeMenuItem(id, theme);
        themeSelector.appendChild(item);
    });
    
    // Divisor
    const divider = document.createElement('li');
    divider.innerHTML = '<hr class="dropdown-divider">';
    themeSelector.appendChild(divider);
    
    // Seção de temas escuros
    const darkThemes = getDarkThemes();
    const darkHeader = document.createElement('li');
    darkHeader.innerHTML = '<h6 class="dropdown-header">Temas Escuros</h6>';
    themeSelector.appendChild(darkHeader);
    
    Object.entries(darkThemes).forEach(([id, theme]) => {
        const item = createThemeMenuItem(id, theme);
        themeSelector.appendChild(item);
    });
}

/**
 * Cria um item de menu para o seletor de temas
 */
function createThemeMenuItem(themeId, theme) {
    const li = document.createElement('li');
    const link = document.createElement('a');
    link.className = 'dropdown-item d-flex align-items-center';
    link.href = '#';
    
    // Verificar se este é o tema atual
    const currentThemeId = localStorage.getItem(DEFAULT_THEME_CONFIG.themeStorageKey);
    if (themeId === currentThemeId) {
        link.classList.add('active');
    }
    
    // Criar amostra de cor do tema
    const colorSwatch = document.createElement('span');
    colorSwatch.className = 'theme-color-swatch me-2';
    colorSwatch.style.backgroundColor = theme.isDark ? '#333' : '#f8f9fa';
    colorSwatch.style.borderColor = theme.isDark ? '#444' : '#dee2e6';
    
    // Adicionar texto
    link.appendChild(colorSwatch);
    link.appendChild(document.createTextNode(theme.name));
    
    // Adicionar evento ao clicar
    link.addEventListener('click', (e) => {
        e.preventDefault();
        switchToTheme(themeId);
        
        // Atualizar itens ativos
        document.querySelectorAll('#themeSelector .dropdown-item').forEach(item => {
            item.classList.remove('active');
        });
        link.classList.add('active');
    });
    
    li.appendChild(link);
    return li;
}

// Iniciar o sistema de temas quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', initThemeSystem);
