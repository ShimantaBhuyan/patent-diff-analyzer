from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, create_engine, JSON, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from urllib.parse import urlparse

from core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DBDocument(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String(10), nullable=False)  # 'Patent A' or 'Patent B'
    filename = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False, default="")
    document_type = Column(String(10), nullable=False)
    raw_text = Column(Text, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    parse_warnings = Column(ARRAY(String), default=list)
    metadata_json = Column(JSON, default=dict)

    claims = relationship("DBClaim", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DBChunk", back_populates="document", cascade="all, delete-orphan")


class DBClaim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True)  # claim_id format: "{doc_id}#C{number}"
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    text = Column(Text, nullable=False)
    claim_type = Column(String(20), nullable=False)
    dependencies = Column(ARRAY(String), default=list)
    source_span_start = Column(Integer)
    source_span_end = Column(Integer)
    source_span_page = Column(Integer)
    metadata_json = Column(JSON, default=dict)

    document = relationship("DBDocument", back_populates="claims")


class DBChunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True)  # chunk_id format: "{doc_id}#chunk{idx}"
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    text = Column(Text, nullable=False)
    token_count = Column(Integer)
    char_offset_start = Column(Integer)
    char_offset_end = Column(Integer)
    section = Column(String(50))
    embedding = Column(Vector(settings.embedding_dimensions))
    metadata_json = Column(JSON, default=dict)

    document = relationship("DBDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_document_id", "document_id"),
    )


class DBAnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), default="pending")
    patent_a_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    patent_b_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    results_json = Column(JSON)
    audit_findings_json = Column(JSON)
    metadata_json = Column(JSON, default=dict)
    saved_name = Column(String(255))
    saved_at = Column(DateTime)


def _ensure_database_exists(database_url: str):
    """Connect to the default 'postgres' database and create the target DB if missing."""
    parsed = urlparse(database_url)
    # Rebuild a connection URL pointing to the default 'postgres' database
    default_url = (
        f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )
    target_db = parsed.path.lstrip("/")
    admin_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db"),
            {"db": target_db},
        ).scalar()
        if not exists:
            # PostgreSQL doesn't support parameterized CREATE DATABASE
            conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    admin_engine.dispose()


def _ensure_columns_exist():
    """Add any missing columns to existing tables (lightweight migrations)."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if "documents" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("documents")}
        if "title" not in columns:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE documents ADD COLUMN title VARCHAR(500) NOT NULL DEFAULT \'\''))
                conn.commit()
                print("Migration: added 'title' column to documents table")


def init_db():
    """Create database (if needed), pgvector extension, and all tables."""
    _ensure_database_exists(settings.database_url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _ensure_columns_exist()
