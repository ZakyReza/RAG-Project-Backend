from pydantic import BaseModel, Field
from typing import Optional

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    use_rag: Optional[bool] = True
    stream: Optional[bool] = False

class DocumentUpload(BaseModel):
    filename: str
    file_type: str