"""Database connection and session management module with resilient fallback."""

import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config import settings

logger = logging.getLogger("ai_agent_harness.database")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_engine(db_url: str = settings.DATABASE_URL):
    """Create SQLAlchemy engine. If PostgreSQL is not reachable, fallback to SQLite."""
    if db_url.startswith("sqlite"):
        os.makedirs("./data", exist_ok=True)
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )

    # For PostgreSQL, check connection with a short timeout
    connect_args = {}
    if "psycopg" in db_url:
        connect_args["connect_timeout"] = 2

    try:
        eng = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args=connect_args,
        )
        # Test connection immediately
        with eng.connect():
            pass
        return eng
    except Exception as e:
        logger.warning(
            f"PostgreSQL connection to {db_url} unavailable ({e}). "
            "Falling back to local SQLite database (data/harness.db)."
        )
        os.makedirs("./data", exist_ok=True)
        return create_engine(
            "sqlite:///./data/harness.db",
            connect_args={"check_same_thread": False},
        )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
