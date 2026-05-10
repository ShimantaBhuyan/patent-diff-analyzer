import asyncio
import io
import re
import os
from typing import List
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import DBDocument, DBChunk, DBClaim
from core.observability import get_logger, Timer
from core.schemas import Document, DocumentType, Chunk, Claim, ClaimType
from api.services.chunking import chunk_text
from api.services.claim_extraction import extract_claims
from api.services.pdf_parser import parse_pdf
from api.services.title_extraction import extract_title

logger = get_logger("ingestion")
settings = get_settings()


async def process_upload(file: UploadFile, label: str, db: Session) -> Document:
    """Process an uploaded file: read, parse, chunk, extract claims.

    Blocking CPU-heavy work (parsing, chunking, claim extraction) is off-loaded
    to a thread so the asyncio event loop stays responsive.
    """
    filename = file.filename or "unknown"

    # Determine document type
    if filename.lower().endswith(".pdf"):
        doc_type = DocumentType.PDF
    else:
        doc_type = DocumentType.TEXT

    # Read file content
    content = await file.read()

    # Check file size
    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > settings.max_file_size_mb:
        raise ValueError(f"File too large: {file_size_mb:.1f}MB (max {settings.max_file_size_mb}MB)")

    # Parse document (may run OCR — CPU intensive)
    with Timer("document_parse"):
        raw_text, parse_warnings = await asyncio.to_thread(
            _parse_document, content, doc_type, filename
        )

    # Extract title (CPU intensive — calls LLM)
    with Timer("title_extraction"):
        title = await asyncio.to_thread(extract_title, raw_text, filename)

    # Create document record
    db_doc = DBDocument(
        label=label,
        filename=filename,
        title=title,
        document_type=doc_type.value,
        raw_text=raw_text,
        parse_warnings=parse_warnings,
        metadata_json={"file_size_mb": round(file_size_mb, 2)},
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    logger.info("Document created: %s (%s)", db_doc.id, filename)

    # Chunk text (CPU intensive)
    with Timer("chunking"):
        chunks = await asyncio.to_thread(chunk_text, raw_text, str(db_doc.id))

    # Persist chunks
    for chunk in chunks:
        db_chunk = DBChunk(
            id=chunk.chunk_id,
            document_id=db_doc.id,
            text=chunk.text,
            token_count=chunk.token_count,
            char_offset_start=chunk.char_offset_start,
            char_offset_end=chunk.char_offset_end,
            section=chunk.section,
            metadata_json=chunk.metadata,
        )
        db.add(db_chunk)

    # Extract claims (CPU intensive — may call LLM)
    with Timer("claim_extraction"):
        claims = await asyncio.to_thread(extract_claims, raw_text, str(db_doc.id))

    # Persist claims (deduplicate by claim_id to avoid DB unique violations)
    seen_ids = set()
    for claim in claims:
        if claim.claim_id in seen_ids:
            logger.warning("Skipping duplicate claim %s", claim.claim_id)
            continue
        seen_ids.add(claim.claim_id)
        db_claim = DBClaim(
            id=claim.claim_id,
            document_id=db_doc.id,
            text=claim.text,
            claim_type=claim.type.value,
            dependencies=claim.dependencies,
            source_span_start=claim.source_span.start_offset if claim.source_span else None,
            source_span_end=claim.source_span.end_offset if claim.source_span else None,
            source_span_page=claim.source_span.page_number if claim.source_span else None,
            metadata_json=claim.metadata,
        )
        db.add(db_claim)

    db.commit()
    logger.info(
        "Document processed: %s - %d chunks, %d claims",
        db_doc.id, len(chunks), len(claims),
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


def _parse_document(content: bytes, doc_type: DocumentType, filename: str) -> tuple:
    """Parse document content to raw text."""
    warnings = []
    
    if doc_type == DocumentType.PDF:
        try:
            text, parse_warnings = parse_pdf(io.BytesIO(content))
            warnings.extend(parse_warnings)
        except Exception as exc:
            logger.warning("PDF parsing failed for %s: %s", filename, exc)
            warnings.append(f"PDF parsing failed: {str(exc)}")
            text = _extract_text_fallback(content)
    else:
        # Plain text
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
            warnings.append("File had encoding issues; replaced invalid characters")
    
    # Basic cleanup
    text = _clean_text(text)
    
    return text, warnings


def _extract_text_fallback(content: bytes) -> str:
    """Fallback text extraction for PDFs."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
        return "\n".join(pages)
    except ImportError:
        logger.warning("PyPDF2 not installed, cannot extract PDF text")
        return ""
    except Exception as exc:
        logger.warning("Fallback PDF extraction failed: %s", exc)
        return ""


def _clean_text(text: str) -> str:
    """Clean extracted text."""
    # Replace multiple whitespace with single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove excessive blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()
