"""Pytest Configuration and Test Fixtures."""

import os
import pytest

# Ensure isolated test database and test configuration before any module imports
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["MOCK_LLM_ENABLED"] = "true"
os.environ["TRUST_THRESHOLD"] = "3"
os.environ["LOG_LEVEL"] = "DEBUG"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import app.database
from app.database import Base, get_db
from app.models.content_queue import ContentQueue
from app.models.trust_store import TrustStore
from app.models.action_log import ActionLog, RestorationLog
from app.models.pending_intent import PendingIntent

# Isolated test database in memory or file
TEST_DB_URL = "sqlite:///./data/test.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Point app.database engine and SessionLocal to test database for tests
app.database.engine = test_engine
app.database.SessionLocal = TestingSessionLocal

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the test database once per session."""
    os.makedirs("./data", exist_ok=True)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./data/test.db"):
        try:
            os.remove("./data/test.db")
        except Exception:
            pass


@pytest.fixture
def db_session():
    """Yield a clean transactional database session per test."""
    session = TestingSessionLocal()
    # Clean tables
    session.query(RestorationLog).delete()
    session.query(ActionLog).delete()
    session.query(PendingIntent).delete()
    session.query(ContentQueue).delete()
    session.query(TrustStore).delete()
    session.commit()

    # Pre-populate default trust counters
    session.add(TrustStore(action_type="purge", success_count=0))
    session.add(TrustStore(action_type="mark_posted", success_count=0))
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
