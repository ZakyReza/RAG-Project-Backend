from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with Pydantic native environment parsing"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
        validate_assignment=True,
    )
    
    # Add LOG_LEVEL that was missing
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Database Configuration
    database_url: str = Field(
        default="sqlite:///./chatbot.db",
        description="Database connection URL"
    )
     
    # Universal LLM Settings
    llm_model: str = Field(
        default="qwen2:0.5b",
        description="Model name to use"
    )
    
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for LLM"
    )
    
    llm_max_tokens: int = Field(
        default=2048,
        gt=0,
        le=32000,
        description="Maximum tokens for LLM response"
    )
    
    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model name"
    )
    
    use_ollama_embeddings: bool = Field(
        default=False,
        description="Use Ollama for embeddings"
    )
    
    # Vector Store Configuration
    chroma_persist_dir: Path = Field(
        default=Path("./chroma_db"),
        description="ChromaDB persistence directory"
    )
    
    chroma_collection_name: str = Field(
        default="documents",
        description="ChromaDB collection name"
    )
    
    # Document Processing
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Text chunk size for document processing"
    )
    
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        description="Overlap between text chunks"
    )
    
    # Retrieval Configuration
    retrieval_k: int = Field(
        default=5,
        gt=0,
        le=20,
        description="Number of documents to retrieve"
    )
    
    rerank_enabled: bool = Field(
        default=True,
        description="Enable re-ranking of retrieved documents"
    )
    
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for retrieval"
    )
    
    # Memory Configuration
    memory_max_tokens: int = Field(
        default=1000,
        gt=0,
        description="Maximum tokens to keep in conversation memory"
    )
    
    # File Upload Configuration
    temp_upload_dir: Path = Field(
        default=Path("./temp_uploads"),
        description="Temporary upload directory"
    )
    
    max_file_size: int = Field(
        default=50 * 1024 * 1024,  
        gt=1024,
        description="Maximum file upload size in bytes"
    )
    
    @field_validator('chunk_overlap')
    @classmethod
    def validate_chunk_overlap(cls, v, info):
        """Ensure chunk overlap is less than chunk size"""
        chunk_size = info.data.get('chunk_size', 1000)
        if v >= chunk_size:
            raise ValueError('Chunk overlap must be less than chunk size')
        return v
    
    @field_validator('chroma_persist_dir', 'temp_upload_dir')
    @classmethod
    def resolve_paths(cls, v):
        """Resolve relative paths to absolute paths"""
        if v is None:
            return v
        return Path(v).resolve()


settings = Settings()