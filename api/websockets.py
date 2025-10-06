from fastapi import WebSocket, WebSocketDisconnect, APIRouter
import json
import logging
from database.session import get_db
from database.models import Conversation, Message
from sqlalchemy.orm import Session
from core.rag_system import SimpleRAGSystem
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize RAG system
rag_system = SimpleRAGSystem()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: int):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
        logger.info(f"WebSocket connected for conversation {conversation_id}")
    
    def disconnect(self, websocket: WebSocket, conversation_id: int):
        if conversation_id in self.active_connections:
            self.active_connections[conversation_id].remove(websocket)
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
        logger.info(f"WebSocket disconnected for conversation {conversation_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)
    
    async def broadcast_to_conversation(self, message: dict, conversation_id: int):
        if conversation_id in self.active_connections:
            for connection in self.active_connections[conversation_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to WebSocket: {e}")
                    

manager = ConnectionManager()

@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: int):
    await manager.connect(websocket, conversation_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "message":
                content = data.get("content", "").strip()
                
                if not content:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Message content cannot be empty"
                    }, websocket)
                    continue
                
                # Send typing indicator
                await manager.broadcast_to_conversation({
                    "type": "typing",
                    "status": True
                }, conversation_id)
                
                try:
                    # Process the message using RAG system
                    result = await rag_system.chat(conversation_id, content)
                    
                    # Save to database
                    db = next(get_db())
                    try:
                        # Save user message
                        user_message = Message(
                            conversation_id=conversation_id,
                            role="user",
                            content=content,
                            retrieval_sources='[]'
                        )
                        db.add(user_message)
                        
                        # Save AI response
                        ai_message = Message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=result["answer"],
                            retrieval_sources=json.dumps(result.get("sources_used", []))
                        )
                        db.add(ai_message)
                        
                        # Update conversation timestamp
                        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                        if conversation:
                            conversation.updated_at = datetime.utcnow()
                        
                        db.commit()
                        
                    except Exception as db_error:
                        db.rollback()
                        logger.error(f"Database error: {db_error}")
                    
                    # Send AI response
                    await manager.broadcast_to_conversation({
                        "type": "message",
                        "content": result["answer"]
                    }, conversation_id)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await manager.broadcast_to_conversation({
                        "type": "error",
                        "message": "Sorry, I encountered an error processing your message"
                    }, conversation_id)
                
                finally:
                    # Stop typing indicator
                    await manager.broadcast_to_conversation({
                        "type": "typing",
                        "status": False
                    }, conversation_id)
            
            elif message_type == "typing":
                # Broadcast typing status to other clients in the same conversation
                await manager.broadcast_to_conversation({
                    "type": "typing",
                    "status": data.get("status", False)
                }, conversation_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, conversation_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, conversation_id)