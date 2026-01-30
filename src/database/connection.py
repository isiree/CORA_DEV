"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from pathlib import Path
import os

from .models import Base

# Database path
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "credentials.db"

# Database URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
# Use StaticPool for SQLite to avoid threading issues
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # For SQLite
    poolclass=StaticPool,
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

def init_database():
    """
    Initialize database tables
    Call this once to create all tables
    """
    print(f"Initializing database at: {DB_PATH}")
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully")

def get_db_session():
    """
    Get a database session
    Use with context manager:
        with get_db_session() as session:
            # do database operations
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_db():
    """
    Simple session getter for non-context-manager use
    Remember to close the session after use!
    """
    return SessionLocal()

def close_db_session():
    """Close the scoped session"""
    SessionLocal.remove()
