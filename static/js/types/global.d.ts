declare namespace API {
    interface User {
        id: number;
        email: string;
        is_staff: boolean;
    }

    interface Token {
        id: number;
        key: string;
        name: string;
        created_at: string;
    }

    interface APILog {
        id: number;
        user_token?: string;
        path: string;
        method: string;
        status_code: number;
        execution_time: number;
        timestamp: string;
    }

    interface AIConfig {
        id: number;
        name: string;
        model_name: string;
        use_system_message: boolean;
        configurations: Record<string, any>;
        training_configurations: Record<string, any>;
    }

    interface APIResponse<T = any> {
        data?: T;
        error?: string;
        message?: string;
    }

    type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

    // Tipos para treinamento
    interface TrainingFile {
        id: number;
        name: string;
        file: string;
        uploaded_at: string;
        file_size?: number;
    }

    interface TrainingCapture {
        id: number;
        token_id: number;
        ai_client_config_id: number;
        is_active: boolean;
        temp_file?: string;
        create_at: string;
        last_activity: string;
    }

    interface TrainingExample {
        system_message: string;
        user_message: string;
        response: string;
    }

    interface AITraining {
        id: number;
        ai_config_id: number;
        file_id?: number;
        job_id: string;
        status: string;
        model_name?: string;
        error?: string;
        created_at: string;
        updated_at: string;
        progress: number;
    }

    // Tipos para solicitações de API
    interface CompareRequest {
        instructor: Record<string, any>;
        students: Record<string, Record<string, any>>;
    }

    interface CompareResponse {
        students: Record<string, Record<string, {
            response: string;
            model_name: string;
            configurations: Record<string, any>;
            processing_time: number;
            error?: string;
        }>>;
    }

    // Tipos para monitoramento
    interface MonitoringData {
        logs: APILog[];
    }

    interface UsageMetrics {
        total_calls: number;
        avg_time: number;
        status_codes: Record<number, number>;
    }

    interface TokenMetrics {
        [token_id: string]: {
            name: string;
            total_calls: number;
            avg_time: number;
            status_codes: Record<number, number>;
        };
    }

    // Tipos para documentos
    interface FileData {
        name: string;
        content: string;
        type: string;
    }

    // Enum como type union
    type TrainingStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
    type DocumentType = 'pdf' | 'docx' | 'txt' | 'json' | 'jsonl';
}
