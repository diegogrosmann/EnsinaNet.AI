interface APPResponse {
    success: boolean;
    error?: string;
    data?: Record<string, any>;
}

interface AIComparisonResponse {
    model_name: string;
    configurations: Record<string, any>;
    processing_time: number;
    response?: string;
    error?: string;
}

type AIComparisonResponseCollection = Record<string, Record<string, AIComparisonResponse>>;

interface APIComparisonResponse extends APPResponse {
    data?: {
        students: AIComparisonResponseCollection;
    };
}
