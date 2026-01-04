from pathlib import Path
import time
import logging
from google.genai import errors as genai_errors
import dotenv
import os
from google import genai
from google.genai import types

env_path = Path(__file__).parent / ".env"
dotenv.load_dotenv(dotenv_path=env_path)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
api_key = os.getenv("GEMINI_API_KEY")


if not api_key:
    print(f"DEBUG: Searching for .env at {env_path.absolute()}")
    raise ValueError("GEMINI_API_KEY not found in environment variables")

client = genai.Client(api_key=api_key)


def _call_gemini_with_retries(parts_or_contents, model=MODEL, max_attempts=5, base_delay=1.0):
    """
    Try calling client.models.generate_content with exponential backoff.
    Returns response on success, raises last exception on permanent failure.
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            resp = client.models.generate_content(model=model, contents=parts_or_contents , config= types.GenerateContentConfig(
                response_mime_type="application/json",))
            return resp
        except genai_errors.ServerError as e:
            # 503 or other server-side transient errors
            attempt += 1
            wait = base_delay * (2 ** (attempt - 1))
            logging.warning("Gemini ServerError attempt %d/%d: %s — retrying in %.1fs", attempt, max_attempts, str(e), wait)
            time.sleep(wait)
        except Exception as e:
            # Non-retryable error — rethrow
            logging.exception("Non-retryable error calling Gemini: %s", e)
            raise
    # If we exit loop, we exhausted retries
    raise genai_errors.ServerError(503, {"error": {"message": "exhausted retries"}}, None)
