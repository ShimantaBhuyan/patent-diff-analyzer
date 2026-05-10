from uuid import UUID
from typing import List
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import DBChunk, DBClaim
from core.observability import get_logger
from core.schemas import Match, Claim

logger = get_logger("retrieval")
settings = get_settings()


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts using OpenAI API."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        
        return [item.embedding for item in response.data]
        
    except ImportError:
        logger.error("OpenAI package not installed")
        raise
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        raise


def retrieve_candidates_for_claim(
    claim: Claim,
    target_document_id: UUID,
    db: Session,
    top_k: int = None,
) -> List[Match]:
    """Retrieve top-k candidate chunks from target document for a given claim.
    
    Uses hybrid scoring: vector similarity + lexical overlap boost.
    """
    if top_k is None:
        top_k = settings.top_k_retrieval
    
    # Generate embedding for the claim
    claim_embeddings = generate_embeddings([claim.text])
    claim_embedding = claim_embeddings[0]
    
    # Vector similarity search using pgvector
    # Order by L2 distance (closer = more similar)
    vector_results = db.query(DBChunk).filter(
        DBChunk.document_id == target_document_id,
        DBChunk.embedding != None,
    ).order_by(
        DBChunk.embedding.l2_distance(claim_embedding)
    ).limit(top_k * 3).all()  # Get more for re-ranking
    
    if not vector_results:
        logger.warning("No vector results for claim %s in document %s", claim.claim_id, target_document_id)
        return []
    
    # Calculate hybrid scores
    matches = []
    for chunk in vector_results:
        # Vector score (convert distance to similarity, normalize to 0-1)
        # L2 distance for normalized vectors: d = sqrt(2 - 2*cosine_similarity)
        # For normalized vectors, cosine_similarity = 1 - (d^2)/2
        # We use a simpler approach: assume vectors are normalized and use inner product
        vector_score = _cosine_similarity(claim_embedding, chunk.embedding)
        
        # Lexical score (simple word overlap)
        lexical_score = _lexical_overlap(claim.text, chunk.text)
        
        # Hybrid score
        hybrid_score = (
            (1 - settings.lexical_boost_weight) * vector_score +
            settings.lexical_boost_weight * lexical_score
        )
        
        match = Match(
            claim_id=claim.claim_id,
            claim_document_id=claim.document_id,
            matched_chunk_id=chunk.id,
            matched_document_id=chunk.document_id,
            vector_score=vector_score,
            lexical_score=lexical_score,
            hybrid_score=hybrid_score,
            matched_text=chunk.text[:200],  # Truncated for brevity
        )
        matches.append(match)
    
    # Sort by hybrid score descending
    matches.sort(key=lambda m: m.hybrid_score, reverse=True)
    
    # Also search against claims in target document
    target_claims = db.query(DBClaim).filter(
        DBClaim.document_id == target_document_id,
    ).all()
    
    for target_claim in target_claims:
        lexical_score = _lexical_overlap(claim.text, target_claim.text)
        if lexical_score > 0.1:  # Only include if some overlap
            # For claims, we use lexical score as proxy (no embeddings stored on claims)
            match = Match(
                claim_id=claim.claim_id,
                claim_document_id=claim.document_id,
                matched_chunk_id=target_claim.id,  # Use claim ID as chunk ID for claims
                matched_document_id=target_claim.document_id,
                vector_score=0.0,  # No vector score for direct claim comparison
                lexical_score=lexical_score,
                hybrid_score=lexical_score * settings.lexical_boost_weight,
                matched_text=target_claim.text[:200],
            )
            matches.append(match)
    
    # Re-sort and take top-k
    matches.sort(key=lambda m: m.hybrid_score, reverse=True)
    top_matches = matches[:top_k]
    
    logger.info(
        "Retrieved %d candidates for claim %s (top hybrid score: %.3f)",
        len(top_matches), claim.claim_id,
        top_matches[0].hybrid_score if top_matches else 0,
    )
    
    return top_matches


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


def _lexical_overlap(text1: str, text2: str) -> float:
    """Calculate lexical overlap between two texts using Jaccard similarity on words."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)
