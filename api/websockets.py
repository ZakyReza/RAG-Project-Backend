from fastapi import WebSocket, WebSocketDisconnect, APIRouter

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: int):
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
    
    def disconnect(self, conversation_id: int):
        self.active_connections.pop(conversation_id, None)
    
    async def send_message(self, message: dict, conversation_id: int):
        if conversation_id in self.active_connections:
            await self.active_connections[conversation_id].send_json(message)

manager = ConnectionManager()

async def websocket_endpoint(websocket: WebSocket, conversation_id: int):
    await manager.connect(websocket, conversation_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            # Send typing indicator
            await manager.send_message({"type": "typing", "status": True}, conversation_id)
            
            # Process message
            response = f"Echo: {message}"
            
            await manager.send_message({
                "type": "message",
                "content": response
            }, conversation_id)
            
            await manager.send_message({"type": "typing", "status": False}, conversation_id)
            
    except WebSocketDisconnect:
        manager.disconnect(conversation_id)
        
@router.websocket("/ws/{conversation_id}")
async def websocket_route(websocket: WebSocket, conversation_id: int):
    await websocket_endpoint(websocket, conversation_id)