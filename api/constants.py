from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AIClientConfig:
    api_key: str
    model_name: str
    base_instruction: str = ""
    prompt: str = ""
    responses: str = ""
    configurations: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True,
    api_url: str = None

@dataclass
class ProcessingResult:
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None

