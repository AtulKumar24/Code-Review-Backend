import hashlib
import logging
from dotenv import load_dotenv
import os
from pathlib import Path
from typing import Any, Dict
# Removed unused imports: from Gemini import _call_gemini_with_retries, time, json, List
# Removed unused/problematic imports: from google.api_core import retry (only need tenacity)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# NEW SDK imports
from google import genai
from google.genai import errors as genai_errors
from google.genai.types import Part
from google.genai import types

from LLM import code_review
from Models import CodeReviewResult, ImageReview, Summary
from Database import store_review # Assume this is where you implement caching

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# Model and client config
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# --- UTILITIES MOVED TO TOP ---
def _guess_mime_type(path: str) -> str:
    # Moved to the top so it is defined when img_code calls it
    ext = Path(path).suffix.lower()
    if ext in {".png"}:
        return "image/png"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "application/octet-stream"

def _extract_code_from_markdown(text: str) -> str:
    # Moved to the top
    import re
    m = re.search(r"```(?:[^\n]*)\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()
# ----------------------------------------------------------------------


# --- RETRY DECORATOR APPLIED TO THE CORE API CALL FUNCTION ---

def is_resource_exhausted(exception) -> bool:
    """
    Checks if the exception is a genai_errors.APIError and contains the 
    RESOURCE_EXHAUSTED message or a 429 status code.
    """
    if isinstance(exception, genai_errors.APIError):
        # Check the message text for the specific error string
        error_message = str(exception)
        return "RESOURCE_EXHAUSTED" in error_message or "429" in error_message
    return False

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=1, max=60), 
    # CRITICAL CHANGE: Only retry on the base APIError. 
    # This catches 4xx and 5xx errors, including the 429/ResourceExhausted.
    retry=retry_if_exception_type(genai_errors.APIError),
    reraise=True 
)
def _call_gemini_extract_code(client, contents, model, config):
    """
    Internal function that makes the actual API call, wrapped by tenacity.
    """
    return client.models.generate_content(
        contents=contents,
        model=model,
        config=config,
    )

# --- MAIN FUNCTION ---
def img_code(user_id: str, img_path: str) -> Dict[str, Any]:
    """
    Extract code from image -> run code review -> store ImageReview.
    """

    # --- 1. Prepare Image and Caching Key ---
    img_bytes = Path(img_path).read_bytes()
    img_hash = hashlib.sha256(img_bytes).hexdigest()

    # NOTE: You MUST implement 'get_from_cache' and 'store_to_cache' 
    # to avoid repeated API calls and save quota.
    # cached_review = get_from_cache(img_hash)
    # if cached_review:
    #     logging.info(f"Cache hit for hash: {img_hash}")
    #     return cached_review # Return ImageReview dict directly

    image_part = types.Part.from_bytes(data=img_bytes, mime_type=_guess_mime_type(img_path))

    extraction_instruction = (
        "Extract ONLY the code from this image. Preserve exact indentation. "
        "Return exactly one markdown code block, nothing else. "
        "If unreadable, mark lines with [UNREADABLE]."
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
    )

    # --- 2. Call Gemini with Retry Wrapper ---
    try:
        response = _call_gemini_extract_code(
            client=client,
            contents=[image_part, extraction_instruction],
            model=MODEL,
            config=config,
        )
    except genai_errors.APIError as e:
        error_message = str(e)
        if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message:
            # Catches the 429 error after all 5 retries have failed
            logging.error(f"Gemini quota exhausted after retries: {e}")
            return {"error": "Image extraction failed (Quota Exhausted)."}
        
        # Handle other API errors (like bad requests, 5xx that tenacity didn't fix)
        logging.exception(f"Gemini API error after retries: {e}")
        return {"error": "Image extraction failed (API Error)."}
        
    except Exception:
        # Catches other non-API errors
        logging.exception("Gemini extraction failed permanently due to unexpected error.")
        return {"error": "Image extraction failed (unexpected error)."}

    # --- 3. Process Response ---
    raw_text = getattr(response, "text", "") or ""
    code_text = _extract_code_from_markdown(raw_text)

    if not code_text.strip():
        logging.error("No code extracted from Gemini response.")
        return {"error": "No code extracted from image", "raw": raw_text[:500]}

    # --- 4. Run existing code review pipeline (Assuming 'code_review' uses a different model/call) ---
    try:
        review_payload = code_review(user_id,code_text)
        review_obj = CodeReviewResult(**review_payload)
    except Exception:
        # ... (fallback review object creation remains the same) ...
        logging.exception("Code review validation failed; creating fallback review.")
        summary = Summary(issueCount=0, criticalCount=0, warningCount=0)
        review_obj = CodeReviewResult(
            summary=summary,
            issues=[],
            codeLength=len(code_text),
            codeLanguage="unknown",
            suggestions=[],
            issuesFound=0,
            raw_code=code_text,
            user_id="",
        )
    
    # --- 5. Finalize and Cache Result ---
    # Convert CodeReviewResult to the final ImageReview dict format (assuming ImageReview is the final type)
    final_review_dict = ImageReview(
        # Assuming ImageReview is a wrapper around the code review result
        review=review_obj,
        image_path=img_path,
    ).dict()

    # store_to_cache(img_hash, final_review_dict) # Conceptual: Store the final result

    return final_review_dict