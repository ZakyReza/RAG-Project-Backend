from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from typing import Generator
import logging
from .models import Base
from config import settings

logger = logging.getLogger(__name__)

# Create engine with proper settings
engine = create_engine(
    settings.database_url,
    echo=(settings.log_level == "DEBUG"),
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create tables at startup
Base.metadata.create_all(bind=engine)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI dependency
def get_db() -> Generator[Session, None, None]:
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction rolled back: {e}")
        raise
    finally:
        db.close()