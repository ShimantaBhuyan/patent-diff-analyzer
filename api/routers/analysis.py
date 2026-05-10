import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
import uuid
from datetime import datetime

from core.config import get_settings
from core.database import get_db, DBAnalysisJob, DBDocument
from core.observability import get_logger, Timer
from core.schemas import AnalysisRequest, AnalysisResponse, ProcessingStatus, DiffResult, AuditFinding, SavedAnalysisSummary, Claim, ClaimType
from api.services.analysis import run_analysis
from core.database import DBDocument, DBClaim

logger = get_logger("analysis")
router = APIRouter()
settings = get_settings()


@router.post("/start", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
):
    """Start a new patent comparison analysis.

    The blocking analysis pipeline (including OpenAI calls) is off-loaded to a
    thread so the asyncio event loop stays responsive.
    """
    patent_a = db.query(DBDocument).filter(DBDocument.id == request.patent_a_id).first()
    patent_b = db.query(DBDocument).filter(DBDocument.id == request.patent_b_id).first()

    if not patent_a or not patent_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both documents not found",
        )

    job = DBAnalysisJob(
        id=uuid.uuid4(),
        status=ProcessingStatus.RUNNING,
        patent_a_id=request.patent_a_id,
        patent_b_id=request.patent_b_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Analysis job started: %s", job.id)

    try:
        with Timer("full_analysis"):
            results = await asyncio.to_thread(
                run_analysis, request.patent_a_id, request.patent_b_id, db
            )

        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.results_json = [r.model_dump(mode="json") for r in results]
        db.commit()

        logger.info("Analysis job completed: %s", job.id)
    except Exception as exc:
        db.rollback()
        logger.exception("Analysis job failed: %s", job.id)
        job.status = ProcessingStatus.FAILED
        job.error_message = str(exc)
        db.commit()

    db.refresh(job)
    return _to_response(job, db)


@router.get("/{job_id}", response_model=AnalysisResponse)
def get_analysis_status(job_id: UUID, db: Session = Depends(get_db)):
    """Get the status and results of an analysis job."""
    job = db.query(DBAnalysisJob).filter(DBAnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )
    return _to_response(job, db)


@router.post("/{job_id}/save", response_model=AnalysisResponse)
def save_analysis(job_id: UUID, name: str, db: Session = Depends(get_db)):
    """Save an analysis job with a given name for future reference."""
    job = db.query(DBAnalysisJob).filter(DBAnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )
    job.saved_name = name
    job.saved_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return _to_response(job, db)


@router.delete("/{job_id}/save", response_model=AnalysisResponse)
def unsave_analysis(job_id: UUID, db: Session = Depends(get_db)):
    """Remove the saved status from an analysis job."""
    job = db.query(DBAnalysisJob).filter(DBAnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )
    job.saved_name = None
    job.saved_at = None
    db.commit()
    db.refresh(job)
    return _to_response(job, db)


@router.get("/saved/list", response_model=list[SavedAnalysisSummary])
def list_saved_analyses(db: Session = Depends(get_db)):
    """List all saved analysis jobs ordered by most recently saved."""
    jobs = (
        db.query(DBAnalysisJob)
        .filter(DBAnalysisJob.saved_name.isnot(None))
        .order_by(DBAnalysisJob.saved_at.desc())
        .all()
    )
    return [
        SavedAnalysisSummary(
            job_id=j.id,
            saved_name=j.saved_name,
            patent_a_id=j.patent_a_id,
            patent_b_id=j.patent_b_id,
            status=ProcessingStatus(j.status),
            created_at=j.created_at,
            saved_at=j.saved_at,
        )
        for j in jobs
    ]


def _to_response(job: DBAnalysisJob, db: Session = None) -> AnalysisResponse:
    results = None
    if job.results_json:
        results = [DiffResult(**r) for r in job.results_json]

    audit_findings = None
    if job.audit_findings_json:
        audit_findings = [AuditFinding(**f) for f in job.audit_findings_json]

    # Look up patent titles and claims
    patent_a_title = ""
    patent_b_title = ""
    patent_a_claims = []
    patent_b_claims = []

    if db is not None:
        doc_a = db.query(DBDocument).filter(DBDocument.id == job.patent_a_id).first()
        doc_b = db.query(DBDocument).filter(DBDocument.id == job.patent_b_id).first()
        if doc_a:
            patent_a_title = doc_a.title or doc_a.filename
            patent_a_claims = [
                Claim(
                    claim_id=c.id,
                    document_id=c.document_id,
                    text=c.text,
                    type=ClaimType(c.claim_type),
                    dependencies=c.dependencies or [],
                )
                for c in doc_a.claims
            ]
        if doc_b:
            patent_b_title = doc_b.title or doc_b.filename
            patent_b_claims = [
                Claim(
                    claim_id=c.id,
                    document_id=c.document_id,
                    text=c.text,
                    type=ClaimType(c.claim_type),
                    dependencies=c.dependencies or [],
                )
                for c in doc_b.claims
            ]

    return AnalysisResponse(
        job_id=job.id,
        status=ProcessingStatus(job.status),
        patent_a_id=job.patent_a_id,
        patent_b_id=job.patent_b_id,
        patent_a_title=patent_a_title,
        patent_b_title=patent_b_title,
        patent_a_claims=patent_a_claims,
        patent_b_claims=patent_b_claims,
        results=results,
        audit_findings=audit_findings,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        saved_name=job.saved_name,
        saved_at=job.saved_at,
    )
