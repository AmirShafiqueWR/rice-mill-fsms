"""
Database Connection Module for Rice Export FSMS

Features:
- Connection pooling (pool_size=5, max_overflow=10)
- Retry logic with exponential backoff for Neon Postgres
- Context manager support for sessions
- Health check and table creation utilities
"""

import os
import time
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

# Load environment variables from .env
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Check your .env file.")

# Create engine with connection pooling optimized for Neon Postgres
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,    # Recycle connections after 5 minutes
    connect_args={
        "sslmode": "require",  # Required for Neon
        "connect_timeout": 10,
    }
)


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)

    Returns:
        Result of the function

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except OperationalError as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"Database connection failed (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"Database connection failed after {max_retries} attempts.")

    raise last_exception


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Usage:
        with get_session() as session:
            session.add(document)
            session.commit()
    """
    session = Session(engine)
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_tables():
    """
    Create all tables defined in SQLModel models.
    Safe to call multiple times - only creates tables that don't exist.
    """
    def _create():
        SQLModel.metadata.create_all(engine)
        return True

    return retry_with_backoff(_create)


def health_check() -> dict:
    """
    Verify database connectivity and return status.

    Returns:
        dict with keys:
            - connected: bool
            - database: str (database name)
            - version: str (PostgreSQL version)
            - error: str (if not connected)
    """
    def _check():
        with Session(engine) as session:
            result = session.execute(text("SELECT version(), current_database()"))
            row = result.fetchone()
            return {
                "connected": True,
                "database": row[1],
                "version": row[0].split(",")[0],
                "error": None
            }

    try:
        return retry_with_backoff(_check)
    except Exception as e:
        return {
            "connected": False,
            "database": None,
            "version": None,
            "error": str(e)
        }


def drop_tables():
    """
    Drop all tables. USE WITH CAUTION - for development only.
    """
    SQLModel.metadata.drop_all(engine)


# Session factory for dependency injection patterns
def get_session_factory():
    """Return a session factory for use with FastAPI or other frameworks."""
    def session_generator():
        with get_session() as session:
            yield session
    return session_generator
