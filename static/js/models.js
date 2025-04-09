// Sistema de tipos para o frontend
// Removendo a verificação condicional para a declaração de ModelRegistry
// Isso pode impedir que seja definida corretamente
const ModelRegistry = {
    types: {},
    
    register: function(typeName, constructor) {
        this.types[typeName] = constructor;
        return constructor;
    },
    
    getType: function(typeName) {
        return this.types[typeName] || null;
    },
    
    deserialize: function(data) {
        if (!data || typeof data !== 'object') {
            return data;
        }
        
        // Log para acompanhar a deserialização
        console.debug("Deserializando:", data);
        
        // Se for um array, deserializa cada item
        if (Array.isArray(data)) {
            return data.map(item => this.deserialize(item));
        }
        
        // Se tiver o campo 'type', instancia o tipo apropriado
        if (data.type && typeof data.type === 'string' && this.types[data.type]) {
            const TypeConstructor = this.types[data.type];
            console.debug(`Criando instância de ${data.type}`);
            return new TypeConstructor(data);
        }
        
        // Objeto regular, deserializa recursivamente suas propriedades
        const result = {};
        for (const key in data) {
            if (data.hasOwnProperty(key)) {
                result[key] = this.deserialize(data[key]);
            }
        }
        return result;
    }
};

// Classe base para todos os modelos
class BaseModel {
    constructor(data = {}) {
        // Copia propriedades, exceto 'type' que já está definido na classe
        for (const key in data) {
            if (key !== 'type' && data.hasOwnProperty(key)) {
                this[key] = ModelRegistry.deserialize(data[key]);
            }
        }
    }
}

// AIExample - Representa um exemplo de prompt/resposta para IA
class AIExample extends BaseModel {
    constructor(data = {}) {
        super(data);
        this.system_message = data.system_message || '';
        this.user_message = data.user_message || '';
        this.response = data.response || '';
    }
}

// AIExampleDict - Dicionário de exemplos de IA
class AIExampleDict extends BaseModel {
    constructor(data = {}) {
        super(data);
        this.examples = [];
        
        // Log para debug
        console.debug("Construindo AIExampleDict com dados:", data);
        
        // Se receber um objeto com exemplos numerados
        if (data && typeof data === 'object') {
            // Se for um array em data.examples
            if (Array.isArray(data.examples)) {
                console.debug("Processando array de exemplos:", data.examples);
                this.examples = ModelRegistry.deserialize(data.examples);
            } 
            // Se tiver exemplos indexados por número (0, 1, 2...)
            else {
                for (const key in data) {
                    if (/^\d+$/.test(key) && data.hasOwnProperty(key)) {
                        console.debug(`Processando exemplo[${key}]:`, data[key]);
                        this.examples.push(ModelRegistry.deserialize(data[key]));
                    }
                }
            }
        }
        console.debug("AIExampleDict construído com exemplos:", this.examples);
    }
}

// Registra os tipos
ModelRegistry.register('AIExample', AIExample);
ModelRegistry.register('AIExampleDict', AIExampleDict);

// Disponibiliza globalmente
window.ModelRegistry = ModelRegistry;
window.AIExample = AIExample;
window.AIExampleDict = AIExampleDict;
window.BaseModel = BaseModel;

// Estende APIResponse para deserializar automaticamente
// IMPORTANTE: Este código deve ser executado DEPOIS que api.js for carregado
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (typeof APIResponse !== 'undefined' && typeof ModelRegistry !== 'undefined') {
            // Verifica se a extensão já foi aplicada para evitar sobreposição
            if (!APIResponse._modelRegistryExtensionApplied) {
                const originalFromJson = APIResponse.from_json;
                
                APIResponse.from_json = function(jsonData) {
                    const response = originalFromJson(jsonData);
                    
                    if (response.success && response.data) {
                        response.data = ModelRegistry.deserialize(response.data);
                    }
                    
                    return response;
                };
                
                APIResponse._modelRegistryExtensionApplied = true;
                console.log('APIResponse estendida com ModelRegistry');
            }
        } else {
            console.error('APIResponse ou ModelRegistry não estão definidos. Verifique a ordem de carregamento dos scripts.');
        }
    }, 100); // Pequeno delay para garantir que todos os scripts foram carregados
});
