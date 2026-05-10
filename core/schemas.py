from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class DocumentType(str, Enum):
    PDF = "pdf"
    TEXT = "text"


class ClaimType(str, Enum):
    INDEPENDENT = "independent"
    DEPENDENT = "dependent"


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Citation(BaseModel):
    """A citation linking a conclusion to source evidence."""
    source_document_id: UUID
    source_document_label: str = Field(description="'Patent A' or 'Patent B'")
    chunk_id: str
    exact_quote: str
    section: Optional[str] = None
    context_window: Optional[str] = None


class SourceSpan(BaseModel):
    """Location of claim text within the original document."""
    start_offset: int
    end_offset: int
    page_number: Optional[int] = None


class Chunk(BaseModel):
    """A text chunk with stable metadata."""
    chunk_id: str
    document_id: UUID
    text: str
    token_count: int
    char_offset_start: int
    char_offset_end: int
    section: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """A processed patent document."""
    document_id: UUID = Field(default_factory=uuid4)
    label: str = Field(description="'Patent A' or 'Patent B'")
    filename: str
    title: str = Field(description="Extracted patent title or filename fallback")
    document_type: DocumentType
    raw_text: str
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    parse_warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Claim(BaseModel):
    """A structured patent claim."""
    claim_id: str
    document_id: UUID
    text: str
    type: ClaimType
    dependencies: List[str] = Field(default_factory=list)
    source_span: Optional[SourceSpan] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Match(BaseModel):
    """A candidate match between a claim and evidence."""
    claim_id: str
    claim_document_id: UUID
    matched_chunk_id: str
    matched_document_id: UUID
    vector_score: float
    lexical_score: float
    hybrid_score: float
    matched_text: str


class DiffResult(BaseModel):
    """Structured diff for a single claim comparison."""
    claim_id: str
    claim_document_id: UUID
    overlap: str = Field(description="Description of overlapping subject matter")
    differences: str = Field(description="Description of differences")
    novelty: str = Field(description="Novelty assessment")
    risk: RiskLevel
    confidence: ConfidenceLevel
    citations: List[Citation] = Field(default_factory=list)
    matched_claims: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None


class AuditFinding(BaseModel):
    """A finding from the audit process."""
    claim_id: str
    severity: str  # "error", "warning", "info"
    finding_type: str
    message: str
    related_citation_ids: List[str] = Field(default_factory=list)
    suggested_action: Optional[str] = None


class AnalysisJob(BaseModel):
    """Tracks the state of an analysis job."""
    job_id: UUID = Field(default_factory=uuid4)
    status: ProcessingStatus = ProcessingStatus.PENDING
    patent_a_id: Optional[UUID] = None
    patent_b_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    results: Optional[List[DiffResult]] = None
    audit_findings: Optional[List[AuditFinding]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    """Request body for starting a new analysis."""
    patent_a_id: UUID
    patent_b_id: UUID


class AnalysisResponse(BaseModel):
    """Response for analysis status/result."""
    job_id: UUID
    status: ProcessingStatus
    patent_a_id: UUID
    patent_b_id: UUID
    patent_a_title: str = ""
    patent_b_title: str = ""
    patent_a_claims: List[Claim] = Field(default_factory=list)
    patent_b_claims: List[Claim] = Field(default_factory=list)
    results: Optional[List[DiffResult]] = None
    audit_findings: Optional[List[AuditFinding]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    saved_name: Optional[str] = None
    saved_at: Optional[datetime] = None


class SavedAnalysisSummary(BaseModel):
    """Summary of a saved analysis for listing."""
    job_id: UUID
    saved_name: str
    patent_a_id: UUID
    patent_b_id: UUID
    status: ProcessingStatus
    created_at: datetime
    saved_at: datetime
