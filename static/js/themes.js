/**
 * Gerenciador de temas Bootswatch
 * Este arquivo contém a lista completa de temas Bootswatch disponíveis
 * e funcionalidades para gerenciá-los.
 */

const BOOTSWATCH_THEMES = {
    "default": {
        name: "Padrão",
        isDark: false,
        url: "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
    },
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

const DEFAULT_THEME_CONFIG = {
    lightTheme: "default",
    darkTheme: "superhero",
    themeStorageKey: "theme",
    themeModeStorageKey: "themeMode"
};

function getAllThemes() {
    return BOOTSWATCH_THEMES;
}

function getLightThemes() {
    return Object.fromEntries(
        Object.entries(BOOTSWATCH_THEMES).filter(([_, theme]) => !theme.isDark)
    );
}

function getDarkThemes() {
    return Object.fromEntries(
        Object.entries(BOOTSWATCH_THEMES).filter(([_, theme]) => theme.isDark)
    );
}

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
    
    const mode = theme.isDark ? 'dark' : 'light';
    localStorage.setItem(DEFAULT_THEME_CONFIG.themeModeStorageKey, mode);
    localStorage.setItem(DEFAULT_THEME_CONFIG.themeStorageKey, themeId);
    
    if (theme.isDark) {
        document.documentElement.classList.add('dark-theme');
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.checked = true;
        }
    } else {
        document.documentElement.classList.remove('dark-theme');
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.checked = false;
        }
    }
    
    return true;
}

function toggleThemeMode() {
    const isDarkMode = document.documentElement.classList.contains('dark-theme');
    const savedLightTheme = localStorage.getItem('lightThemeId') || DEFAULT_THEME_CONFIG.lightTheme;
    const savedDarkTheme = localStorage.getItem('darkThemeId') || DEFAULT_THEME_CONFIG.darkTheme;
    
    if (isDarkMode) {
        switchToTheme(savedLightTheme);
    } else {
        switchToTheme(savedDarkTheme);
    }
}

function initThemeSystem() {
    let themeLink = document.getElementById('themeLink');
    if (!themeLink) {
        themeLink = document.createElement('link');
        themeLink.id = 'themeLink';
        themeLink.rel = 'stylesheet';
        document.head.appendChild(themeLink);
    }
    
    const savedTheme = localStorage.getItem(DEFAULT_THEME_CONFIG.themeStorageKey);
    const savedMode = localStorage.getItem(DEFAULT_THEME_CONFIG.themeModeStorageKey);
    const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    let initialTheme;
    if (savedTheme && BOOTSWATCH_THEMES[savedTheme]) {
        initialTheme = savedTheme;
    } else if (savedMode) {
        initialTheme = savedMode === 'dark' ? DEFAULT_THEME_CONFIG.darkTheme : DEFAULT_THEME_CONFIG.lightTheme;
    } else {
        initialTheme = prefersDarkMode ? DEFAULT_THEME_CONFIG.darkTheme : DEFAULT_THEME_CONFIG.lightTheme;
    }
    
    switchToTheme(initialTheme);
    
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!savedTheme && !savedMode) {
            const newTheme = e.matches ? DEFAULT_THEME_CONFIG.darkTheme : DEFAULT_THEME_CONFIG.lightTheme;
            switchToTheme(newTheme);
        }
    });
    
    populateThemeSelector();
}

function populateThemeSelector() {
    const themeSelector = document.getElementById('themeSelector');
    if (!themeSelector) return;
    
    themeSelector.innerHTML = '';
    
    const lightThemes = getLightThemes();
    const lightHeader = document.createElement('li');
    lightHeader.innerHTML = '<h6 class="dropdown-header">Temas Claros</h6>';
    themeSelector.appendChild(lightHeader);
    
    Object.entries(lightThemes).forEach(([id, theme]) => {
        const item = createThemeMenuItem(id, theme);
        themeSelector.appendChild(item);
    });
    
    const divider = document.createElement('li');
    divider.innerHTML = '<hr class="dropdown-divider">';
    themeSelector.appendChild(divider);
    
    const darkThemes = getDarkThemes();
    const darkHeader = document.createElement('li');
    darkHeader.innerHTML = '<h6 class="dropdown-header">Temas Escuros</h6>';
    themeSelector.appendChild(darkHeader);
    
    Object.entries(darkThemes).forEach(([id, theme]) => {
        const item = createThemeMenuItem(id, theme);
        themeSelector.appendChild(item);
    });
}

function createThemeMenuItem(themeId, theme) {
    const li = document.createElement('li');
    const link = document.createElement('a');
    link.className = 'dropdown-item d-flex align-items-center';
    link.href = '#';
    
    const currentThemeId = localStorage.getItem(DEFAULT_THEME_CONFIG.themeStorageKey);
    if (themeId === currentThemeId) {
        link.classList.add('active');
    }
    
    const colorSwatch = document.createElement('span');
    colorSwatch.className = 'theme-color-swatch me-2';
    // Adiciona classe de acordo com o tipo do tema (evitando CSS inline)
    colorSwatch.classList.add(theme.isDark ? 'theme-swatch-dark' : 'theme-swatch-light');
    
    link.appendChild(colorSwatch);
    link.appendChild(document.createTextNode(theme.name));
    
    link.addEventListener('click', (e) => {
        e.preventDefault();
        switchToTheme(themeId);
        
        document.querySelectorAll('#themeSelector .dropdown-item').forEach(item => {
            item.classList.remove('active');
        });
        link.classList.add('active');
    });
    
    li.appendChild(link);
    return li;
}

document.addEventListener('DOMContentLoaded', initThemeSystem);
