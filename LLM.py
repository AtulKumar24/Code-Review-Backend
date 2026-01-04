from datetime import datetime
import logging
import dotenv
from fastapi import HTTPException
import json
from Gemini import _call_gemini_with_retries
from Models import CodeReviewResult
from Database import store_review
from typing import Any, Dict, List
from pathlib import Path
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv


load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")



CODE_REVIEW_SYSTEM_PROMPT = """
You are an expert senior software engineer and code reviewer.

Your job:
- Analyze the given source code.
- Find bugs, security issues, performance problems, and style issues.
- Explain each issue clearly.
- Suggest an improved version of the code where needed.

You MUST respond with a single JSON object in this exact structure,
with ALL fields present:

{
  "summary": {
    "issueCount": number,
    "criticalCount": number,
    "warningCount": number
  },
  "issues": [
    {
      "id": "string",
      "line": number,
      "severity": "critical" | "warning" | "info",
      "category": "bug" | "security" | "performance" | "style" | "maintainability" | "other",
      "title": "short title of the issue",
      "explanation": "clear explanation of what is wrong and why",
      "suggestedFix": "code snippet showing the improved version"
    }
  ],
  "codeLength": number,
  "codeLanguage": "string",
  "suggestions": ["list", "of", "general", "suggestions"],
  "issuesFound": number,
  "improved_code": "string",
}

Rules:
- If there are no issues, use 0 for counts, an empty issues array [],
  and an empty suggestions array [].
- Do NOT include any text before or after the JSON.
"""




def _normalize_issue(raw: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Ensure each issue is a dict with required keys and sensible defaults."""
    return {
        "id": str(raw.get("id") or str(idx + 1)),
        "line": str(raw.get("line") or "0"),  # STRING for Flutter
        "severity": str(raw.get("severity") or "info"),
        "category": str(raw.get("category") or "other"),
        "title": str(raw.get("title") or "Issue"),
        "explanation": str(raw.get("explanation") or ""),
        "suggestedFix": str(raw.get("suggestedFix") or ""),
    }


def _normalize_payload(data: Dict[str, Any], code: str, language: str | None, user_id: str) -> Dict[str, Any]:
    lang = language or data.get("codeLanguage") or "unknown"
    issues_raw = data.get("issues") or []
    
    # Normalize each issue found by AI
    issues: List[Dict[str, Any]] = [_normalize_issue(i, idx) for idx, i in enumerate(issues_raw)]

    # Final shape for MongoDB and Flutter
    return {
        "user_id": user_id,
        "raw_code": code,
        "codeLanguage": lang,
        "codeLength": len(code),
        "issuesFound": len(issues), # Use snake_case here to match your field name
        "summary": {
            "issueCount": len(issues),
            "criticalCount": sum(1 for i in issues if i["severity"] == "critical"),
            "warningCount": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "issues": issues,
        "suggestions": data.get("suggestions") or [],
        "improved_code": data.get("improved_code") or "",
        "created_at": datetime.utcnow()
    }

def code_review(code: str, user_id: str, language: str | None = None) -> dict:
    user_prompt = f"Code language: {language or 'auto'}\n\nCode:\n```{code}```"

    try:
        # Call with your retry logic
        response = _call_gemini_with_retries([CODE_REVIEW_SYSTEM_PROMPT, user_prompt])
        raw_text = response.text if response.text else "{}"
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, Exception) as e:
        if "429" in str(e):
            raise HTTPException(status_code=429, detail="AI Quota exhausted. Please try again later.")
        logging.error(f"AI Review Error: {e}")
        parsed = {} # Fallback to empty if AI fails

    # Normalize including the user context
    final_payload = _normalize_payload(parsed, code, language, user_id)

    
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(final_payload)



        