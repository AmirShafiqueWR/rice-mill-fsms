"""
FastAPI Application for Rice Export FSMS (ISO 22001:2018)

Features:
- Document and Task CRUD endpoints
- Validation with Pydantic schemas
- Audit trail support
- Health check endpoint
- CORS configuration
- Automatic OpenAPI documentation at /docs
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select, func

from database import get_session, health_check as db_health_check
from models import Document, Task, VALID_DEPARTMENTS, STATUS_TRANSITIONS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI application
app = FastAPI(
    title="Rice Export FSMS API",
    description="Food Safety Management System API for Rice Export - ISO 22001:2018 Compliant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error_code: str
    detail: str


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    doc_id: str = Field(..., description="Unique document identifier (e.g., FSMS-SOP-001)")
    title: str = Field(..., description="Document title")
    department: str = Field(..., description="Department: Milling, Quality, Exports, Packaging, Storage")
    version: str = Field(..., description="Version format: v1.0, v1.1, v2.0")
    prepared_by: str = Field(..., description="Person who prepared the document")
    approved_by: str = Field(..., description="Person who approved the document")
    record_keeper: str = Field(..., description="Person responsible for record keeping")
    review_cycle_months: int = Field(default=12, description="Review cycle in months")
    iso_clauses: Optional[List[str]] = Field(default=None, description="List of ISO clause numbers")
    file_path: Optional[str] = Field(default=None, description="Path to document file")

    @field_validator("department")
    @classmethod
    def validate_department(cls, v):
        if v not in VALID_DEPARTMENTS:
            raise ValueError(f"Department must be one of: {VALID_DEPARTMENTS}")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v):
        if not re.match(r'^v\d+\.\d+$', v):
            raise ValueError("Version must match format v1.0, v1.1, v2.0, etc.")
        return v


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    status: Optional[str] = Field(default=None, description="Status: Draft, Controlled, Obsolete")
    version: Optional[str] = Field(default=None, description="Version format: v1.0, v1.1")
    approval_date: Optional[datetime] = Field(default=None, description="Approval date")
    file_path: Optional[str] = Field(default=None, description="Path to document file")
    file_hash: Optional[str] = Field(default=None, description="SHA-256 hash of file")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in ["Draft", "Controlled", "Obsolete"]:
            raise ValueError("Status must be one of: Draft, Controlled, Obsolete")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v):
        if v and not re.match(r'^v\d+\.\d+$', v):
            raise ValueError("Version must match format v1.0, v1.1, v2.0, etc.")
        return v


class DocumentResponse(BaseModel):
    """Schema for document response."""
    id: int
    doc_id: str
    title: str
    department: str
    version: str
    status: str
    prepared_by: str
    approved_by: str
    record_keeper: str
    approval_date: Optional[datetime]
    review_cycle_months: int
    iso_clauses: Optional[str]
    file_path: Optional[str]
    file_hash: Optional[str]
    created_at: datetime
    updated_at: datetime
    version_hash: Optional[str]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""
    total: int
    documents: List[DocumentResponse]


class TaskCreate(BaseModel):
    """Schema for creating a task."""
    document_id: int = Field(..., description="ID of parent document")
    task_description: str = Field(..., description="Full task description from document")
    action: Optional[str] = Field(default=None, description="Extracted action verb")
    object: Optional[str] = Field(default=None, description="Object of the action")
    iso_clause: str = Field(..., description="ISO clause reference (required)")
    critical_limit: Optional[str] = Field(default=None, description="Critical limit value")
    frequency: Optional[str] = Field(default=None, description="Task frequency")
    assigned_department: str = Field(..., description="Department responsible")
    assigned_role: Optional[str] = Field(default=None, description="Role responsible")
    priority: str = Field(default="Medium", description="Priority: Critical, High, Medium, Low")
    source_document_version: Optional[str] = Field(default=None, description="Document version")
    extracted_from_page: Optional[int] = Field(default=None, description="Page number in document")

    @field_validator("iso_clause")
    @classmethod
    def validate_iso_clause(cls, v):
        if not v or not v.strip():
            raise ValueError("ISO clause is required and cannot be empty")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v not in ["Critical", "High", "Medium", "Low"]:
            raise ValueError("Priority must be one of: Critical, High, Medium, Low")
        return v


class TaskBulkCreate(BaseModel):
    """Schema for bulk task creation."""
    tasks: List[TaskCreate]


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    status: Optional[str] = Field(default=None, description="Status: Pending, Completed, Overdue")
    priority: Optional[str] = Field(default=None, description="Priority level")
    assigned_role: Optional[str] = Field(default=None, description="Assigned role")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in ["Pending", "Completed", "Overdue"]:
            raise ValueError("Status must be one of: Pending, Completed, Overdue")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v and v not in ["Critical", "High", "Medium", "Low"]:
            raise ValueError("Priority must be one of: Critical, High, Medium, Low")
        return v


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: int
    document_id: int
    task_description: str
    action: Optional[str]
    object: Optional[str]
    iso_clause: str
    critical_limit: Optional[str]
    frequency: Optional[str]
    assigned_department: str
    assigned_role: Optional[str]
    priority: str
    status: str
    source_document_version: Optional[str]
    extracted_from_page: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskBulkResponse(BaseModel):
    """Schema for bulk task creation response."""
    created_count: int
    task_ids: List[int]


class DocumentWithTasks(BaseModel):
    """Schema for document with its tasks."""
    document: DocumentResponse
    tasks: List[TaskResponse]


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    database: Optional[str]
    version: Optional[str]
    timestamp: datetime


class AuditEntry(BaseModel):
    """Schema for audit trail entry."""
    document_id: int
    doc_id: str
    version: str
    status: str
    updated_at: datetime
    version_hash: Optional[str]


# ============================================================================
# Dependency
# ============================================================================

def get_db():
    """Database session dependency."""
    with get_session() as session:
        yield session


# ============================================================================
# Request/Response Logging Middleware
# ============================================================================

@app.middleware("http")
async def log_requests(request, call_next):
    """Log all incoming requests and responses."""
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# ============================================================================
# System Endpoints
# ============================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health Check",
    description="Check API and database health status"
)
async def health_check():
    """
    Health check endpoint to verify API and database connectivity.

    Returns database connection status and PostgreSQL version.
    """
    db_status = db_health_check()
    return HealthResponse(
        status="healthy" if db_status["connected"] else "unhealthy",
        database=db_status["database"],
        version=db_status["version"],
        timestamp=datetime.utcnow()
    )


# ============================================================================
# Document Endpoints
# ============================================================================

@app.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
    summary="Create Document",
    description="Create a new controlled document",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Database error"}
    }
)
async def create_document(doc: DocumentCreate, db: Session = Depends(get_db)):
    """
    Create a new document for ISO 22001:2018 compliance.

    Example:
    ```json
    {
        "doc_id": "FSMS-SOP-001",
        "title": "Milling Procedures",
        "department": "Milling",
        "version": "v1.0",
        "prepared_by": "Quality Manager",
        "approved_by": "Plant Director",
        "record_keeper": "Document Control"
    }
    ```
    """
    # Check for duplicate doc_id
    existing = db.exec(select(Document).where(Document.doc_id == doc.doc_id)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "DUPLICATE_DOC_ID", "detail": f"Document with doc_id '{doc.doc_id}' already exists"}
        )

    # Create document
    document = Document(
        doc_id=doc.doc_id,
        title=doc.title,
        department=doc.department,
        version=doc.version,
        prepared_by=doc.prepared_by,
        approved_by=doc.approved_by,
        record_keeper=doc.record_keeper,
        review_cycle_months=doc.review_cycle_months,
        file_path=doc.file_path
    )

    if doc.iso_clauses:
        document.set_iso_clauses(doc.iso_clauses)

    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(f"Created document: {document.doc_id}")
    return document


@app.get(
    "/documents",
    response_model=DocumentListResponse,
    tags=["Documents"],
    summary="List Documents",
    description="Get all documents with optional filters"
)
async def list_documents(
    department: Optional[str] = Query(None, description="Filter by department"),
    status: Optional[str] = Query(None, description="Filter by status"),
    version: Optional[str] = Query(None, description="Filter by version"),
    approved_by: Optional[str] = Query(None, description="Filter by approver"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: Session = Depends(get_db)
):
    """
    List all documents with pagination and filters.

    Query Parameters:
    - department: Filter by department name
    - status: Filter by document status
    - version: Filter by version number
    - approved_by: Filter by approver name
    - limit: Max results (default 50, max 100)
    - offset: Results offset for pagination
    """
    query = select(Document)

    if department:
        query = query.where(Document.department == department)
    if status:
        query = query.where(Document.status == status)
    if version:
        query = query.where(Document.version == version)
    if approved_by:
        query = query.where(Document.approved_by == approved_by)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.exec(count_query).one()

    # Get paginated results
    query = query.offset(offset).limit(limit).order_by(Document.created_at.desc())
    documents = db.exec(query).all()

    return DocumentListResponse(total=total, documents=documents)


@app.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    tags=["Documents"],
    summary="Get Document",
    description="Get a single document by ID",
    responses={404: {"model": ErrorResponse, "description": "Document not found"}}
)
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a single document by its ID."""
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Document with id {document_id} not found"}
        )
    return document


@app.patch(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    tags=["Documents"],
    summary="Update Document",
    description="Update document fields (status, version, approval_date, file_path, file_hash)",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid status transition"},
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def update_document(document_id: int, update: DocumentUpdate, db: Session = Depends(get_db)):
    """
    Update document fields.

    Status transitions are one-way only:
    - Draft → Controlled → Obsolete

    Cannot transition backwards.
    """
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Document with id {document_id} not found"}
        )

    # Validate status transition
    if update.status and update.status != document.status:
        if not document.can_transition_to(update.status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_TRANSITION",
                    "detail": f"Cannot transition from '{document.status}' to '{update.status}'. Allowed: {STATUS_TRANSITIONS.get(document.status, [])}"
                }
            )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(document, key, value)

    document.updated_at = datetime.utcnow()
    document.update_version_hash()

    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(f"Updated document: {document.doc_id}")
    return document


@app.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Documents"],
    summary="Soft Delete Document",
    description="Soft delete document by setting status to Obsolete (preserves audit trail)",
    responses={404: {"model": ErrorResponse, "description": "Document not found"}}
)
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """
    Soft delete a document.

    Sets status to 'Obsolete' instead of actually deleting.
    This preserves the audit trail for ISO compliance.
    """
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Document with id {document_id} not found"}
        )

    document.status = "Obsolete"
    document.updated_at = datetime.utcnow()
    document.update_version_hash()

    db.add(document)
    db.commit()

    logger.info(f"Soft deleted document: {document.doc_id}")
    return None


@app.get(
    "/documents/{document_id}/tasks",
    response_model=DocumentWithTasks,
    tags=["Documents"],
    summary="Get Document with Tasks",
    description="Get document with all linked tasks (eager loading)",
    responses={404: {"model": ErrorResponse, "description": "Document not found"}}
)
async def get_document_with_tasks(document_id: int, db: Session = Depends(get_db)):
    """Get a document with all its associated tasks."""
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Document with id {document_id} not found"}
        )

    # Get tasks for this document
    tasks = db.exec(select(Task).where(Task.document_id == document_id)).all()

    return DocumentWithTasks(document=document, tasks=tasks)


# ============================================================================
# Task Endpoints
# ============================================================================

@app.post(
    "/tasks",
    response_model=TaskBulkResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
    summary="Bulk Create Tasks",
    description="Create multiple tasks at once",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def create_tasks(bulk: TaskBulkCreate, db: Session = Depends(get_db)):
    """
    Bulk create tasks.

    Example:
    ```json
    {
        "tasks": [
            {
                "document_id": 1,
                "task_description": "Check moisture content",
                "iso_clause": "8.5.1",
                "assigned_department": "Quality",
                "priority": "Critical"
            }
        ]
    }
    ```
    """
    created_ids = []

    for task_data in bulk.tasks:
        # Verify document exists
        document = db.get(Document, task_data.document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "NOT_FOUND", "detail": f"Document with id {task_data.document_id} not found"}
            )

        task = Task(
            document_id=task_data.document_id,
            task_description=task_data.task_description,
            action=task_data.action,
            object=task_data.object,
            iso_clause=task_data.iso_clause,
            critical_limit=task_data.critical_limit,
            frequency=task_data.frequency,
            assigned_department=task_data.assigned_department,
            assigned_role=task_data.assigned_role,
            priority=task_data.priority,
            source_document_version=task_data.source_document_version,
            extracted_from_page=task_data.extracted_from_page
        )

        db.add(task)
        db.flush()  # Get ID without committing
        created_ids.append(task.id)

    db.commit()
    logger.info(f"Created {len(created_ids)} tasks")

    return TaskBulkResponse(created_count=len(created_ids), task_ids=created_ids)


@app.get(
    "/tasks",
    response_model=List[TaskResponse],
    tags=["Tasks"],
    summary="List Tasks",
    description="Get all tasks with optional filters"
)
async def list_tasks(
    document_id: Optional[int] = Query(None, description="Filter by document ID"),
    department: Optional[str] = Query(None, description="Filter by department"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    iso_clause: Optional[str] = Query(None, description="Filter by ISO clause"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: Session = Depends(get_db)
):
    """List tasks with optional filters and pagination."""
    query = select(Task)

    if document_id:
        query = query.where(Task.document_id == document_id)
    if department:
        query = query.where(Task.assigned_department == department)
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if iso_clause:
        query = query.where(Task.iso_clause == iso_clause)

    query = query.offset(offset).limit(limit).order_by(Task.created_at.desc())
    tasks = db.exec(query).all()

    return tasks


@app.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["Tasks"],
    summary="Get Task",
    description="Get a single task by ID",
    responses={404: {"model": ErrorResponse, "description": "Task not found"}}
)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a single task by its ID."""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Task with id {task_id} not found"}
        )
    return task


@app.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["Tasks"],
    summary="Update Task",
    description="Update task fields (status, priority, assigned_role)",
    responses={404: {"model": ErrorResponse, "description": "Task not found"}}
)
async def update_task(task_id: int, update: TaskUpdate, db: Session = Depends(get_db)):
    """Update task fields."""
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Task with id {task_id} not found"}
        )

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info(f"Updated task: {task.id}")
    return task


# ============================================================================
# Audit Trail Endpoint
# ============================================================================

@app.get(
    "/audit-trail/{document_id}",
    response_model=List[AuditEntry],
    tags=["System"],
    summary="Get Audit Trail",
    description="Get document audit trail (version history)",
    responses={404: {"model": ErrorResponse, "description": "Document not found"}}
)
async def get_audit_trail(document_id: int, db: Session = Depends(get_db)):
    """
    Get audit trail for a document.

    Returns version history showing all document states.
    Note: Full audit trail requires additional audit logging implementation.
    """
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "NOT_FOUND", "detail": f"Document with id {document_id} not found"}
        )

    # Return current state as audit entry
    # Full implementation would require audit log table
    return [
        AuditEntry(
            document_id=document.id,
            doc_id=document.doc_id,
            version=document.version,
            status=document.status,
            updated_at=document.updated_at,
            version_hash=document.version_hash
        )
    ]


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent error format."""
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=detail
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": "ERROR", "detail": str(detail)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": "INTERNAL_ERROR", "detail": "An unexpected error occurred"}
    )


# ============================================================================
# Run with FastAPI CLI (recommended)
# ============================================================================
# Development: uv run fastapi dev main.py --port 8000
# Production:  uv run fastapi run main.py --port 8000
