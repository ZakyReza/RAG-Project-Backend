from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    retrieval_sources: List[Dict[str, Any]] = []
    timestamp: datetime

    @field_validator('retrieval_sources', mode='before')
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v

    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    message: MessageResponse
    conversation_id: int
    sources_used: Optional[List[Dict[str, Any]]]
    answer: str

class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    chunk_count: int
    processed: bool
    uploaded_at: datetime

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str

class SearchResult(BaseModel):
    content: str
    metadata: Dict[str, Any]
    relevance_score: float

