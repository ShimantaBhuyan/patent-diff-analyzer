import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from core.database import get_db, DBAnalysisJob
from core.observability import get_logger, Timer
from core.schemas import AnalysisResponse, ProcessingStatus, AuditFinding
from api.services.audit import run_audit

logger = get_logger("audit")
router = APIRouter()


@router.post("/{job_id}", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def audit_analysis(
    job_id: UUID,
    db: Session = Depends(get_db),
):
    """Run an audit on a completed analysis."""
    job = db.query(DBAnalysisJob).filter(DBAnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found",
        )

    if job.status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analysis must be completed before auditing",
        )

    if not job.results_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No results to audit",
        )

    logger.info("Audit started for job: %s", job_id)

    try:
        with Timer("audit"):
            findings = await asyncio.to_thread(run_audit, job, db)

        job.audit_findings_json = [f.model_dump() for f in findings]
        job.updated_at = datetime.utcnow()
        db.commit()

        logger.info("Audit completed for job: %s, findings=%d", job_id, len(findings))
    except Exception as exc:
        logger.exception("Audit failed for job: %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit failed: {str(exc)}",
        )

    db.refresh(job)

    # Return updated response
    from api.routers.analysis import _to_response
    return _to_response(job, db)
