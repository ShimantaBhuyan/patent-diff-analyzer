import re
import tiktoken
from typing import List

from core.config import get_settings
from core.schemas import Chunk

settings = get_settings()


def chunk_text(text: str, document_id: str) -> List[Chunk]:
    """Split text into overlapping chunks with stable metadata."""
    encoder = tiktoken.get_encoding("cl100k_base")

    tokens = encoder.encode(text)
    total_tokens = len(tokens)
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap

    chunks: List[Chunk] = []
    start = 0
    chunk_idx = 0
    search_pos = 0  # cursor in original text for text.find()

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text_str = encoder.decode(chunk_tokens)

        # Find the chunk's position in the original text starting from our
        # current search cursor.  This avoids the O(n²) decode-from-start
        # pattern that killed performance on large documents.
        char_start = text.find(chunk_text_str, search_pos)
        if char_start == -1:
            # Fallback: if the exact chunk text can't be found (rare, can
            # happen with ambiguous Unicode or whitespace normalisation),
            # approximate using the previous end or the search cursor.
            char_start = search_pos
        char_end = char_start + len(chunk_text_str)

        chunk = Chunk(
            chunk_id=f"{document_id}#chunk{chunk_idx}",
            document_id=document_id,
            text=chunk_text_str,
            token_count=len(chunk_tokens),
            char_offset_start=char_start,
            char_offset_end=char_end,
            section=_detect_section(chunk_text_str),
            metadata={
                "chunk_index": chunk_idx,
                "total_chunks": None,
            },
        )
        chunks.append(chunk)

        # Advance the search cursor to the end of the *non-overlapping* part
        # of this chunk so the next chunk is found nearby in the text.
        non_overlap_end = char_start + len(encoder.decode(tokens[start:end - chunk_overlap]))
        search_pos = max(search_pos, non_overlap_end)

        chunk_idx += 1
        if end == total_tokens:
            break
        start = end - chunk_overlap

    for chunk in chunks:
        chunk.metadata["total_chunks"] = len(chunks)

    return chunks


def _detect_section(text: str) -> str:
    """Detect which patent section a chunk belongs to."""
    text_upper = text.upper()

    if re.search(r'\bCLAIMS?\b', text_upper):
        return "claims"
    if re.search(r'\bABSTRACT\b', text_upper):
        return "abstract"
    if re.search(r'\bSUMMARY\b', text_upper):
        return "summary"
    if re.search(r'\bDESCRIPTION\b', text_upper):
        return "description"
    if re.search(r'\bBACKGROUND\b', text_upper):
        return "background"
    if re.search(r'\bDETAILED\s+DESCRIPTION\b', text_upper):
        return "detailed_description"

    if re.search(r'\b(claim\s+\d+|wherein|comprising|consisting)\b', text, re.IGNORECASE):
        return "claims"

    return "unknown"
