from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import DBAnalysisJob, DBChunk
from core.observability import get_logger
from core.schemas import (
    AuditFinding, DiffResult, Citation, RiskLevel, ConfidenceLevel
)

logger = get_logger("audit")
settings = get_settings()


def run_audit(job: DBAnalysisJob, db: Session) -> List[AuditFinding]:
    """Run an audit on a completed analysis job."""
    findings = []
    
    if not job.results_json:
        return findings
    
    results = [DiffResult(**r) for r in job.results_json]
    
    for result in results:
        # Check 1: Unsupported conclusions (high risk without citations)
        if result.risk == RiskLevel.HIGH and not result.citations:
            findings.append(AuditFinding(
                claim_id=result.claim_id,
                severity="error",
                finding_type="unsupported_conclusion",
                message=f"HIGH risk claim '{result.claim_id}' has no citations.",
                related_citation_ids=[],
                suggested_action="Add citations or downgrade risk to UNKNOWN.",
            ))
        
        # Check 2: Invalid citations (citations that don't map to real chunks)
        for citation in result.citations:
            chunk = db.query(DBChunk).filter(DBChunk.id == citation.chunk_id).first()
            if not chunk:
                findings.append(AuditFinding(
                    claim_id=result.claim_id,
                    severity="error",
                    finding_type="invalid_citation",
                    message=f"Citation chunk_id '{citation.chunk_id}' does not exist in database.",
                    related_citation_ids=[citation.chunk_id],
                    suggested_action="Remove invalid citation or verify chunk_id.",
                ))
            else:
                # Check 3: Citation text mismatch
                if citation.exact_quote and citation.exact_quote not in chunk.text:
                    # Allow for some whitespace variation
                    normalized_quote = " ".join(citation.exact_quote.split())
                    normalized_chunk = " ".join(chunk.text.split())
                    if normalized_quote not in normalized_chunk:
                        findings.append(AuditFinding(
                            claim_id=result.claim_id,
                            severity="warning",
                            finding_type="citation_mismatch",
                            message=f"Citation quote does not appear in chunk '{citation.chunk_id}'.",
                            related_citation_ids=[citation.chunk_id],
                            suggested_action="Verify exact quote or chunk assignment.",
                        ))
        
        # Check 4: Overstated confidence
        if result.confidence == ConfidenceLevel.HIGH:
            if len(result.citations) < 2:
                findings.append(AuditFinding(
                    claim_id=result.claim_id,
                    severity="warning",
                    finding_type="overstated_confidence",
                    message=f"HIGH confidence with only {len(result.citations)} citation(s).",
                    related_citation_ids=[c.chunk_id for c in result.citations],
                    suggested_action="Add more supporting citations or downgrade confidence.",
                ))
        
        # Check 5: Weak semantic matches (low hybrid scores)
        # This is a heuristic - if the top match has very low score
        if result.confidence != ConfidenceLevel.INSUFFICIENT_EVIDENCE:
            # We don't have direct access to scores in the result, but we can check
            # if the result seems weak based on reasoning length
            if result.reasoning and len(result.reasoning) < 50:
                findings.append(AuditFinding(
                    claim_id=result.claim_id,
                    severity="warning",
                    finding_type="weak_reasoning",
                    message="Reasoning is very short; may indicate weak analysis.",
                    related_citation_ids=[],
                    suggested_action="Expand reasoning with more detail.",
                ))
    
    logger.info("Audit complete: %d findings for job %s", len(findings), job.id)
    return findings
