from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import json

Base = declarative_base()

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), default="New Conversation", nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", lazy="dynamic")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_conversation_updated', 'updated_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
        }
    

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    retrieval_sources = Column(Text, nullable=True, default='[]')
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    
    conversation = relationship("Conversation", back_populates="messages")
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_message_conversation', 'conversation_id'),
        Index('idx_message_timestamp', 'timestamp'),
        Index('idx_message_role', 'role'),
    )
    
    def to_dict(self):
        try:
            # Safely parse retrieval_sources from JSON string to list
            if self.retrieval_sources:
                sources = json.loads(self.retrieval_sources)
            else:
                sources = []
        except (json.JSONDecodeError, TypeError, ValueError):
            sources = []  # Fallback to empty list

        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'retrieval_sources': sources,
            'timestamp': self.timestamp,
        }

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True)  # MD5 hash
    
    # Processing information
    chunk_count = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    processing_status = Column(String(20), default='pending', nullable=False)  # 'pending', 'processing', 'completed', 'failed'

    
    # Timestamps
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)
    
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_document_hash', 'content_hash'),
        Index('idx_document_processed', 'processed'),
        Index('idx_document_uploaded', 'uploaded_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'content_hash': self.content_hash,
            'file_size': self.file_size,
            'chunk_count': self.chunk_count,
            'total_tokens': self.total_tokens,
            'processed': self.processed,
            'processing_status': self.processing_status,
            'uploaded_at': self.uploaded_at,
        }