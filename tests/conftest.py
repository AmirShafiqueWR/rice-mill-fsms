"""
Pytest Configuration and Fixtures for Rice Export FSMS

Features:
- Test database isolation from production
- Session-scoped database setup/teardown
- Reusable fixtures for documents and tasks
- FastAPI TestClient setup
"""

import os
import pytest
from datetime import datetime
from typing import Generator

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

# Load test environment
from dotenv import load_dotenv
load_dotenv()

# Import application components
from main import app, get_db
from models import Document, Task


# ============================================================================
# Test Database Configuration
# ============================================================================

# Use test database URL or fallback to in-memory SQLite
DATABASE_URL_TEST = os.getenv("DATABASE_URL_TEST", "sqlite:///:memory:")

# Create test engine
if DATABASE_URL_TEST.startswith("sqlite"):
    # SQLite needs special configuration for testing
    test_engine = create_engine(
        DATABASE_URL_TEST,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL test database
    test_engine = create_engine(
        DATABASE_URL_TEST,
        echo=False,
        pool_pre_ping=True,
    )


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables at start of test session, drop at end."""
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Provide a clean database session for each test.
    Rolls back all changes after each test.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def clean_db(test_db: Session) -> Session:
    """
    Fixture that ensures a clean database state.
    Deletes all records before yielding session.
    """
    test_db.query(Task).delete()
    test_db.query(Document).delete()
    test_db.commit()
    return test_db


# ============================================================================
# FastAPI TestClient Fixture
# ============================================================================

@pytest.fixture(scope="function")
def test_client(test_db: Session) -> Generator[TestClient, None, None]:
    """
    Provide FastAPI TestClient with test database.
    Overrides the get_db dependency to use test database.
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_document_data() -> dict:
    """Return valid document data for testing."""
    return {
        "doc_id": "FSMS-TEST-001",
        "title": "Test Document",
        "department": "Quality",
        "version": "v1.0",
        "prepared_by": "Test User",
        "approved_by": "Test Approver",
        "record_keeper": "Test Keeper",
        "review_cycle_months": 12,
    }


@pytest.fixture
def sample_document(test_db: Session, sample_document_data: dict) -> Document:
    """Create and return a sample document in the database."""
    document = Document(**sample_document_data)
    test_db.add(document)
    test_db.commit()
    test_db.refresh(document)
    return document


@pytest.fixture
def sample_task_data(sample_document: Document) -> dict:
    """Return valid task data for testing."""
    return {
        "document_id": sample_document.id,
        "task_description": "Test task description",
        "action": "test",
        "object": "test object",
        "iso_clause": "8.5.1",
        "critical_limit": "Test limit",
        "frequency": "Daily",
        "assigned_department": "Quality",
        "assigned_role": "Inspector",
        "priority": "High",
        "source_document_version": sample_document.version,
    }


@pytest.fixture
def sample_task(test_db: Session, sample_document: Document, sample_task_data: dict) -> Task:
    """Create and return a sample task in the database."""
    task = Task(**sample_task_data)
    test_db.add(task)
    test_db.commit()
    test_db.refresh(task)
    return task


@pytest.fixture
def multiple_documents(test_db: Session) -> list[Document]:
    """Create multiple documents for list/filter testing."""
    documents = [
        Document(
            doc_id="FSMS-MILL-001",
            title="Milling Procedure",
            department="Milling",
            version="v1.0",
            status="Draft",
            prepared_by="Mill Manager",
            approved_by="Plant Director",
            record_keeper="Doc Control",
        ),
        Document(
            doc_id="FSMS-QA-001",
            title="Quality Inspection",
            department="Quality",
            version="v2.0",
            status="Controlled",
            prepared_by="QA Lead",
            approved_by="QA Director",
            record_keeper="QA Admin",
        ),
        Document(
            doc_id="FSMS-EXP-001",
            title="Export Guidelines",
            department="Exports",
            version="v1.1",
            status="Obsolete",
            prepared_by="Export Manager",
            approved_by="CEO",
            record_keeper="Export Admin",
        ),
    ]
    for doc in documents:
        test_db.add(doc)
    test_db.commit()
    for doc in documents:
        test_db.refresh(doc)
    return documents


@pytest.fixture
def multiple_tasks(test_db: Session, sample_document: Document) -> list[Task]:
    """Create multiple tasks for list/filter testing."""
    tasks = [
        Task(
            document_id=sample_document.id,
            task_description="Critical moisture check",
            iso_clause="8.5.1",
            assigned_department="Quality",
            priority="Critical",
            status="Pending",
        ),
        Task(
            document_id=sample_document.id,
            task_description="Temperature monitoring",
            iso_clause="7.2",
            assigned_department="Milling",
            priority="High",
            status="Completed",
        ),
        Task(
            document_id=sample_document.id,
            task_description="Documentation review",
            iso_clause="4.4",
            assigned_department="Quality",
            priority="Medium",
            status="Overdue",
        ),
    ]
    for task in tasks:
        test_db.add(task)
    test_db.commit()
    for task in tasks:
        test_db.refresh(task)
    return tasks
