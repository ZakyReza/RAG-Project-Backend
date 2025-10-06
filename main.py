from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
from api.websockets import router as ws_router
from config import settings
import uvicorn
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Server starting up...")
    logger.info("📍 API routes available at: /api/*")
    logger.info("🔌 WebSocket available at: /ws/{conversation_id}")
    logger.info("🌐 CORS enabled for: localhost:3000, localhost:5173")
    
    yield  # Server runs here
    
    # Shutdown
    logger.info("👋 Server shutting down gracefully...")



# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # WebSocket origins
        "ws://localhost:3000",
        "ws://127.0.0.1:3000",
        "ws://localhost:5173",
        "ws://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(ws_router)

@app.get("/")
async def root():
    return {"message": "RAG Backend API"}

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        ws_ping_interval=20,
        ws_ping_timeout=20,
        log_level="info"
    )