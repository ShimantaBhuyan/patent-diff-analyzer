from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from uuid import UUID
import uuid

from core.database import get_db, DBDocument
from core.observability import get_logger, Timer
from core.schemas import Document, DocumentType
from api.services.ingestion import process_upload

logger = get_logger("documents")
router = APIRouter()


@router.post("/upload", response_model=Document, status_code=status.HTTP_201_CREATED)
async def upload_document(
    label: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a patent document (PDF or text)."""
    if label not in ("Patent A", "Patent B"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label must be 'Patent A' or 'Patent B'",
        )
    
    with Timer("document_upload"):
        doc = await process_upload(file, label, db)
    
    logger.info("Document uploaded: %s (%s)", doc.document_id, doc.filename)
    return doc


@router.get("/{document_id}", response_model=Document)
def get_document(document_id: UUID, db: Session = Depends(get_db)):
    """Retrieve a document by ID."""
    db_doc = db.query(DBDocument).filter(DBDocument.id == document_id).first()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return Document(
        document_id=db_doc.id,
        label=db_doc.label,
        filename=db_doc.filename,
        title=db_doc.title,
        document_type=DocumentType(db_doc.document_type),
        raw_text=db_doc.raw_text,
        upload_timestamp=db_doc.upload_timestamp,
        parse_warnings=db_doc.parse_warnings or [],
        metadata=db_doc.metadata_json or {},
    )
