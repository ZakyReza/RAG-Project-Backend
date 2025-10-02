from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, WebSocket
from sqlalchemy.orm import Session
from datetime import datetime
import json
import hashlib
import asyncio
import logging 

from database.session import get_db
from database.models import Conversation, Message, Document
from core.rag_system import SimpleRAGSystem
from schemas.request import ConversationCreate, MessageCreate 
from schemas.response import ConversationResponse, MessageResponse, ChatResponse, DocumentResponse
from utils.file_handlers import file_handler
from api.websockets import websocket_endpoint, manager

router = APIRouter()
rag_system = SimpleRAGSystem()
logger = logging.getLogger(__name__)

# Conversation routes
@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db)
):
    db_conversation = Conversation(title=conversation.title)
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation

@router.get("/conversations", response_model=list[ConversationResponse])
async def get_conversations(db: Session = Depends(get_db)):
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return conversations

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return conversation

@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.timestamp).all()

    return messages

@router.post("/conversations/{conversation_id}/chat", response_model=ChatResponse)
async def chat(
    conversation_id: int,
    message: MessageCreate,  
    db: Session = Depends(get_db)
):
    if not rag_system:
        raise HTTPException(500, "RAG system not available")
    
    # Verify conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    
    try:
        # Check if this is the first user message
        existing_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.role == "user"
        ).count()
        
        # Save user message
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=message.content,
            retrieval_sources='[]'
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        # Get AI response
        result = await rag_system.chat(conversation_id, message.content)
    
        # Save AI message
        ai_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=result["answer"],
            retrieval_sources=json.dumps(result.get("sources_used", []))
        )
        db.add(ai_message)
        
        # Update conversation title if this is the first message
        if existing_messages == 0 and conversation.title == "New Conversation":
            try:

                title_prompt = f"Generate a concise title (maximum 6 words) for a conversation that starts with this question: '{message.content[:100]}'. Only respond with the title, nothing else."

                title_result = await asyncio.to_thread(
                    rag_system.llm.invoke, 
                    title_prompt
                )
                
                if hasattr(title_result, 'content'):
                    generated_title = title_result.content.strip()
                else:
                    generated_title = str(title_result).strip()
                
                generated_title = generated_title.strip('"\'').strip()
                if len(generated_title) > 60:
                    generated_title = generated_title[:60] + "..."
                
                conversation.title = generated_title
                
            except Exception as title_error:
                logger.warning(f"Failed to generate smart title: {title_error}")

                fallback_title = message.content[:50] + "..." if len(message.content) > 50 else message.content
                conversation.title = fallback_title
    
        # Update conversation timestamp and commit all changes
        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ai_message)

        return ChatResponse(
            conversation_id=conversation_id,
            message=ai_message.to_dict(),
            answer=result["answer"],
            sources_used=result.get("sources_used", [])
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        db.rollback()
        raise HTTPException(500, f"Error processing chat message: {str(e)}")
    
# Document routes
@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    try:
        # Check if document already exists
        content = await file.read()
        await file.seek(0)  
        file_hash = hashlib.md5(content).hexdigest()
        
        existing_doc = db.query(Document).filter(Document.content_hash == file_hash).first()
        if existing_doc:
            return DocumentResponse(
                id=existing_doc.id,
                filename=existing_doc.filename,
                original_filename=existing_doc.original_filename,
                file_type=existing_doc.file_type,
                chunk_count=existing_doc.chunk_count,
                processed=existing_doc.processed,
                uploaded_at=existing_doc.uploaded_at
            )
        
        file_info = await file_handler.save_upload_file(file)
        file_path = file_info["path"] 

        logger.info(f"File saved to: {file_path}, type: {type(file_path)}")

        chunk_count = await rag_system.add_documents([file_path])
        
        # Create document record
        db_doc = Document(
            filename=file_path, 
            original_filename=file.filename,
            file_type=file.content_type,
            content_hash=file_hash,
            chunk_count=chunk_count,
            processed=chunk_count > 0
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        
        return DocumentResponse(
            id=db_doc.id,
            filename=db_doc.filename,
            original_filename=db_doc.original_filename,
            file_type=db_doc.file_type,
            chunk_count=db_doc.chunk_count,
            processed=db_doc.processed,
            uploaded_at=db_doc.uploaded_at
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing file: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        # Always cleanup temp file
        file_handler.cleanup_file(file_info["path"])

@router.get("/documents", response_model=list[DocumentResponse])
async def get_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            chunk_count=doc.chunk_count,
            processed=doc.processed,
            uploaded_at=doc.uploaded_at
        ) for doc in documents
    ]

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """Delete a conversation and its messages"""
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    
    # Clear memory for this conversation
    if rag_system and hasattr(rag_system, 'memory_manager'):
        await rag_system.memory_manager.clear_memory(conversation_id)
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted successfully"}

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document from database and vector store"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(404, "Document not found")
    
    try:
        # Delete from vector store
        if rag_system and rag_system.vectorstore:
            try:
                rag_system.vectorstore.delete(
                    where={"source": document.filename}
                )
                logger.info(f"Deleted document chunks from vector store: {document.filename}")
            except Exception as ve:
                logger.warning(f"Could not delete from vector store: {ve}")
        
        # Delete from database
        db.delete(document)
        db.commit()
        
        return {"message": "Document deleted successfully", "id": document_id}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(500, f"Error deleting document: {str(e)}")
