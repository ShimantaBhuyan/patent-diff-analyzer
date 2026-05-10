import re
from typing import List, Optional

from core.config import get_settings
from core.observability import get_logger
from core.schemas import Claim, ClaimType, SourceSpan

logger = get_logger("claim_extraction")
settings = get_settings()


def extract_claims(text: str, document_id: str) -> List[Claim]:
    """Extract structured claims from patent text.
    
    Strategy:
    1. Rule-based extraction for numbered claims
    2. LLM cleanup/normalization for noisy formatting (optional)
    """
    # First, try to find claims section
    claims_section = _extract_claims_section(text)
    
    if not claims_section:
        logger.warning("No claims section found in document %s", document_id)
        return []
    
    # Rule-based extraction of numbered claims
    claims = _extract_numbered_claims(claims_section, document_id)
    
    if not claims:
        logger.warning("No numbered claims extracted from document %s", document_id)
        return []
    
    # Determine claim types (independent vs dependent)
    claims = _classify_claim_types(claims)
    
    logger.info("Extracted %d claims from document %s", len(claims), document_id)
    return claims


def _extract_claims_section(text: str) -> str:
    """Extract the claims section from patent text."""
    # Look for "Claims" or "What is claimed" headers
    patterns = [
        r'(?:^|\n)\s*CLAIMS?\s*(?:\n|$)(.*?)(?=\n\s*(?:ABSTRACT|DESCRIPTION|BACKGROUND|SUMMARY|DETAILED)\s*(?:\n|$))',
        r'(?:^|\n)\s*What\s+is\s+claimed\s*[:;]?(.*?)(?=\n\s*(?:ABSTRACT|DESCRIPTION|BACKGROUND|SUMMARY|DETAILED)\s*(?:\n|$))',
        r'(?:^|\n)\s*We\s+claim\s*[:;]?(.*?)(?=\n\s*(?:ABSTRACT|DESCRIPTION|BACKGROUND|SUMMARY|DETAILED)\s*(?:\n|$))',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # Fallback: look for numbered claims anywhere in text
    # If we find a pattern like "1. A method...", use the rest of the text
    claim_start = re.search(r'(?:^|\n)\s*1\.\s+[A-Z]', text)
    if claim_start:
        return text[claim_start.start():]
    
    return ""


def _extract_numbered_claims(text: str, document_id: str) -> List[Claim]:
    """Extract numbered claims using regex patterns."""
    claims = []
    
    # Pattern for claim numbers followed by text
    # Matches patterns like "1. A method..." or "1.  A method..."
    pattern = r'(?:^|\n)\s*(\d+)\.\s+(.*?)(?=\n\s*\d+\.\s+(?=[A-Z])|\Z)'
    
    matches = list(re.finditer(pattern, text, re.DOTALL))
    
    for match in matches:
        claim_number = match.group(1)
        claim_text = match.group(2).strip()
        
        # Clean up claim text
        claim_text = re.sub(r'\s+', ' ', claim_text)
        
        if len(claim_text) < 10:
            logger.warning("Claim %s is suspiciously short: %s", claim_number, claim_text[:50])
            continue
        if len(claim_text) > 5000:
            logger.warning(
                "Claim %s is suspiciously long (%d chars); likely a false positive — skipping",
                claim_number,
                len(claim_text),
            )
            continue
        
        claim = Claim(
            claim_id=f"{document_id}#C{claim_number}",
            document_id=document_id,
            text=claim_text,
            type=ClaimType.INDEPENDENT,  # Default, will be updated
            dependencies=[],
            source_span=SourceSpan(
                start_offset=match.start(),
                end_offset=match.end(),
                page_number=None,
            ),
            metadata={"claim_number": claim_number},
        )
        claims.append(claim)
    
    return claims


def _classify_claim_types(claims: List[Claim]) -> List[Claim]:
    """Classify claims as independent or dependent."""
    for claim in claims:
        text_lower = claim.text.lower()
        
        # Check for dependency language
        # Patterns: "claim 1", "claims 1 and 2", "claim 1, wherein"
        dep_match = re.search(
            r'(?:claim|claims)\s+(\d+(?:\s+(?:and|or)\s+\d+)*)',
            text_lower,
        )
        
        if dep_match:
            claim.type = ClaimType.DEPENDENT
            # Extract dependency numbers
            dep_str = dep_match.group(1)
            deps = re.findall(r'\d+', dep_str)
            claim.dependencies = deps
            
            # Remove dependency preamble from text for cleaner comparison
            # Keep the "wherein" part
            wherein_match = re.search(r'(wherein|further|additionally)', text_lower)
            if wherein_match:
                start_idx = wherein_match.start()
                claim.text = claim.text[start_idx:]
        else:
            claim.type = ClaimType.INDEPENDENT
    
    return claims
