from uuid import UUID
from typing import List
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import DBDocument, DBClaim, DBChunk
from core.observability import get_logger, Timer
from core.schemas import (
    DiffResult, Claim, Citation, RiskLevel, ConfidenceLevel,
    Chunk as ChunkSchema, Match
)
from api.services.retrieval import retrieve_candidates_for_claim, generate_embeddings

logger = get_logger("analysis")
settings = get_settings()


def run_analysis(patent_a_id: UUID, patent_b_id: UUID, db: Session) -> List[DiffResult]:
    """Run the full analysis pipeline between two patents."""
    
    # Load documents
    doc_a = db.query(DBDocument).filter(DBDocument.id == patent_a_id).first()
    doc_b = db.query(DBDocument).filter(DBDocument.id == patent_b_id).first()
    
    if not doc_a or not doc_b:
        raise ValueError("One or both documents not found")
    
    logger.info("Starting analysis: %s vs %s", patent_a_id, patent_b_id)
    
    # Load claims
    claims_a = db.query(DBClaim).filter(DBClaim.document_id == patent_a_id).all()
    claims_b = db.query(DBClaim).filter(DBClaim.document_id == patent_b_id).all()
    
    if not claims_a:
        logger.warning("No claims found for Patent A: %s", patent_a_id)
    if not claims_b:
        logger.warning("No claims found for Patent B: %s", patent_b_id)
    
    # Generate embeddings for all chunks if not already present
    with Timer("generate_embeddings"):
        _ensure_embeddings(db, patent_a_id)
        _ensure_embeddings(db, patent_b_id)
    
    # For each claim in A, find matches and reason
    results = []
    for db_claim_a in claims_a:
        claim_a = Claim(
            claim_id=db_claim_a.id,
            document_id=db_claim_a.document_id,
            text=db_claim_a.text,
            type=db_claim_a.claim_type,
            dependencies=db_claim_a.dependencies or [],
            metadata=db_claim_a.metadata_json or {},
        )
        
        with Timer(f"analyze_claim_{claim_a.claim_id}"):
            result = _analyze_single_claim(claim_a, patent_b_id, db)
        
        results.append(result)
    
    logger.info("Analysis complete: %d claims analyzed", len(results))
    return results


def _ensure_embeddings(db: Session, document_id: UUID):
    """Generate embeddings for chunks that don't have them."""
    chunks = db.query(DBChunk).filter(
        DBChunk.document_id == document_id,
        DBChunk.embedding == None,
    ).all()
    
    if not chunks:
        return
    
    texts = [c.text for c in chunks]
    embeddings = generate_embeddings(texts)
    
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding
    
    db.commit()
    logger.info("Generated embeddings for %d chunks in document %s", len(chunks), document_id)


def _analyze_single_claim(
    claim_a: Claim,
    patent_b_id: UUID,
    db: Session,
) -> DiffResult:
    """Analyze a single claim against Patent B."""
    
    # Retrieve candidates
    with Timer("retrieval"):
        candidates = retrieve_candidates_for_claim(claim_a, patent_b_id, db)
    
    if not candidates:
        logger.warning("No candidates found for claim %s", claim_a.claim_id)
        return DiffResult(
            claim_id=claim_a.claim_id,
            claim_document_id=claim_a.document_id,
            overlap="No overlapping subject matter found.",
            differences="Unable to determine differences due to lack of comparable claims.",
            novelty="Novelty assessment requires comparable claims.",
            risk=RiskLevel.UNKNOWN,
            confidence=ConfidenceLevel.INSUFFICIENT_EVIDENCE,
            citations=[],
            matched_claims=[],
            reasoning="No relevant claims found in Patent B for comparison.",
        )
    
    # Build reasoning prompt
    with Timer("reasoning"):
        result = _reason_about_claim(claim_a, candidates, patent_b_id, db)
    
    return result


def _reason_about_claim(
    claim_a: Claim,
    candidates: List[Match],
    patent_b_id: UUID,
    db: Session,
) -> DiffResult:
    """Use LLM to reason about claim overlap and differences."""
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
    except ImportError:
        logger.error("OpenAI package not installed")
        return _fallback_result(claim_a, candidates)
    except Exception as exc:
        logger.error("Failed to initialize OpenAI client: %s", exc)
        return _fallback_result(claim_a, candidates)
    
    # Build prompt with strict citation requirements
    evidence_text, chunk_id_map = _build_evidence_text(candidates, db)
    
    prompt = f"""You are a patent analysis assistant. Analyze the following claim from Patent A against the evidence from Patent B.

CLAIM FROM PATENT A:
{claim_a.text}

EVIDENCE FROM PATENT B:
{evidence_text}

INSTRUCTIONS:
1. Analyze the overlap between the claim and the evidence
2. Identify key differences
3. Assess novelty
4. Evaluate infringement risk (High/Medium/Low/Unknown)
5. Provide confidence level (High/Medium/Low/insufficient_evidence)
6. CITE specific evidence using the EXACT chunk_id strings shown above (e.g. "E1", "E2", ...).

RULES:
- You may ONLY use the provided evidence. Do not hallucinate citations.
- Every conclusion must have at least one citation.
- If evidence is weak or insufficient, say "insufficient evidence".
- The chunk_id in each citation MUST be exactly one of the evidence labels shown (E1, E2, ...).

Respond in this exact JSON format:
{{
    "overlap": "description of overlapping subject matter",
    "differences": "description of key differences",
    "novelty": "novelty assessment",
    "risk": "High|Medium|Low|Unknown",
    "confidence": "High|Medium|Low|insufficient_evidence",
    "citations": [
        {{
            "source_document_id": "patent_b_id",
            "source_document_label": "Patent B",
            "chunk_id": "E1",
            "exact_quote": "exact text from evidence",
            "section": "section name"
        }}
    ],
    "matched_claims": ["claim_id_1", "claim_id_2"],
    "reasoning": "step-by-step reasoning"
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a precise patent analyst. Only use provided evidence. Never hallucinate citations."},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            response_format={"type": "json_object"},
        )
        
        import json
        content = response.choices[0].message.content
        result_data = json.loads(content)
        
        # Validate and normalize
        result = _validate_reasoning_result(claim_a, result_data, candidates, chunk_id_map, patent_b_id)
        return result
        
    except Exception as exc:
        logger.exception("Reasoning failed for claim %s: %s", claim_a.claim_id, exc)
        return _fallback_result(claim_a, candidates)


def _build_evidence_text(candidates: List[Match], db: Session):
    """Build evidence text from candidates.
    
    Returns a tuple of (evidence_text, chunk_id_map) where chunk_id_map maps
    the short label used in the prompt (e.g. "E1") to the real chunk ID.
    """
    evidence_parts = []
    chunk_id_map: dict = {}  # label -> real chunk id
    
    for i, match in enumerate(candidates[:settings.top_k_retrieval]):
        label = f"E{i+1}"
        chunk_id_map[label] = match.matched_chunk_id
        # Get chunk details
        chunk = db.query(DBChunk).filter(DBChunk.id == match.matched_chunk_id).first()
        text_preview = chunk.text[:500] if chunk else match.matched_text
        evidence_parts.append(
            f"[{label}] Score: {match.hybrid_score:.3f}\n"
            f"    Text: {text_preview}\n"
        )
    
    return "\n".join(evidence_parts), chunk_id_map


def _validate_reasoning_result(
    claim_a: Claim,
    result_data: dict,
    candidates: List[Match],
    chunk_id_map: dict = None,
    patent_b_id: UUID = None,
) -> DiffResult:
    """Validate and normalize the reasoning result."""
    
    # Map string values to enums
    risk_str = result_data.get("risk", "Unknown").lower()
    confidence_str = result_data.get("confidence", "insufficient_evidence").lower()
    
    risk_map = {
        "high": RiskLevel.HIGH,
        "medium": RiskLevel.MEDIUM,
        "low": RiskLevel.LOW,
        "unknown": RiskLevel.UNKNOWN,
    }
    confidence_map = {
        "high": ConfidenceLevel.HIGH,
        "medium": ConfidenceLevel.MEDIUM,
        "low": ConfidenceLevel.LOW,
        "insufficient_evidence": ConfidenceLevel.INSUFFICIENT_EVIDENCE,
    }
    
    risk = risk_map.get(risk_str, RiskLevel.UNKNOWN)
    confidence = confidence_map.get(confidence_str, ConfidenceLevel.INSUFFICIENT_EVIDENCE)
    
    # Validate citations — resolve short labels (E1, E2, …) to real chunk IDs
    citations = []
    valid_chunk_ids = {c.matched_chunk_id for c in candidates}
    label_map = chunk_id_map or {}  # label -> real chunk id
    
    for citation_data in result_data.get("citations", []):
        raw_chunk_id = citation_data.get("chunk_id", "")
        # Resolve label to real chunk id if needed
        chunk_id = label_map.get(raw_chunk_id, raw_chunk_id)
        if chunk_id in valid_chunk_ids:
            # Use the actual patent_b_id instead of whatever the LLM returned
            doc_id = patent_b_id if patent_b_id else citation_data.get("source_document_id", "")
            citations.append(Citation(
                source_document_id=doc_id,
                source_document_label=citation_data.get("source_document_label", "Patent B"),
                chunk_id=chunk_id,
                exact_quote=citation_data.get("exact_quote", ""),
                section=citation_data.get("section"),
            ))
        else:
            logger.warning("Invalid citation chunk_id: %s (resolved from label: %s)", chunk_id, raw_chunk_id)
    
    # If no valid citations and confidence is high, downgrade
    if not citations and confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM):
        confidence = ConfidenceLevel.INSUFFICIENT_EVIDENCE
        logger.warning("No valid citations found, downgrading confidence for claim %s", claim_a.claim_id)
    
    return DiffResult(
        claim_id=claim_a.claim_id,
        claim_document_id=claim_a.document_id,
        overlap=result_data.get("overlap", ""),
        differences=result_data.get("differences", ""),
        novelty=result_data.get("novelty", ""),
        risk=risk,
        confidence=confidence,
        citations=citations,
        matched_claims=result_data.get("matched_claims", []),
        reasoning=result_data.get("reasoning", ""),
    )


def _fallback_result(claim_a: Claim, candidates: List[Match]) -> DiffResult:
    """Generate a fallback result when reasoning fails."""
    return DiffResult(
        claim_id=claim_a.claim_id,
        claim_document_id=claim_a.document_id,
        overlap="Analysis failed. Manual review required.",
        differences="Analysis failed. Manual review required.",
        novelty="Analysis failed. Manual review required.",
        risk=RiskLevel.UNKNOWN,
        confidence=ConfidenceLevel.INSUFFICIENT_EVIDENCE,
        citations=[],
        matched_claims=[c.matched_chunk_id for c in candidates[:3]],
        reasoning="LLM reasoning failed. Fallback to manual review.",
    )
