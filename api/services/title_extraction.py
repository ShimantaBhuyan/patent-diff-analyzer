import re
from typing import Optional

from core.config import get_settings
from core.observability import get_logger

logger = get_logger("title_extraction")
settings = get_settings()


def extract_title(raw_text: str, filename: str) -> str:
    """Extract patent title from document text using OpenAI, fallback to filename."""
    # Take first ~4000 chars which usually covers the first page
    first_page = raw_text[:4000]
    
    if not first_page.strip():
        logger.warning("No text available for title extraction, using filename")
        return filename
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
    except ImportError:
        logger.warning("OpenAI package not installed, using filename as title")
        return filename
    except Exception as exc:
        logger.error("Failed to initialize OpenAI client for title extraction: %s", exc)
        return filename
    
    prompt = f"""You are a patent document assistant. Given the first page of a patent document, extract the patent title.

RULES:
- Return ONLY the title string, nothing else.
- If no clear title is found, return "UNKNOWN".
- Do not include quotes, explanations, or JSON.
- Use the exact title as it appears in the document.

FIRST PAGE TEXT:
{first_page}

TITLE:"""

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You extract patent titles from document text. Return only the title."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=100,
        )
        
        title = response.choices[0].message.content.strip()
        # Clean up common LLM artifacts
        title = re.sub(r'^[\'"]+|[\'"]+$', '', title)
        title = title.strip()
        
        if title and title.lower() != "unknown":
            logger.info("Extracted title: %s", title)
            return title
        else:
            logger.warning("Could not extract title from text, using filename")
            return filename
            
    except Exception as exc:
        logger.exception("Title extraction failed: %s", exc)
        return filename
