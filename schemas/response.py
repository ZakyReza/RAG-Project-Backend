from pydantic import BaseModel
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
    retrieval_sources: Optional[List[Dict[str, Any]]]
    timestamp: datetime

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