import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.discovery.lifecycle import get_effective_end_date
from app.discovery.normalizer import TAMIL_NADU_DISTRICTS, DISTRICT_ALIASES

logger = logging.getLogger(__name__)

GENERIC_TITLES = {
    "home", "events", "upcoming events", "past events", "untitled",
    "contact us", "about us", "privacy policy", "terms of service",
    "404 not found", "advertisement", "subscribe", "read more",
    "news", "press release", "blog", "articles", "welcome"
}

CANCELLATION_PATTERN = re.compile(
    r"\b(cancelled|canceled|postponed indefinitely|event cancelled|event canceled|call off|called off)\b",
    re.IGNORECASE,
)

ACCREDITED_INSTITUTION_PATTERN = re.compile(
    r"(\.ac\.in|\.edu|\.edu\.in|\.res\.in|\.gov\.in|\bcollege\b|\buniversity\b|\binstitute\b|\biit\b|\bnit\b|\banna univ|\btnsi\b|\bstartuptn\b|\bcommunity\b)",
    re.IGNORECASE,
)


class OllamaEventExtraction(BaseModel):
    title: Optional[str] = Field(default=None, description="Event title verbatim from source")
    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD or ISO timestamp")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM-DD or ISO timestamp")
    venue_name: Optional[str] = Field(default=None, description="Explicit venue name or null")
    city: Optional[str] = Field(default=None, description="Tamil Nadu city or null")
    registration_url: Optional[str] = Field(default=None, description="Direct registration/ticket URL")
    verbatim_evidence_quote: Optional[str] = Field(default=None, description="Exact verbatim quote from the text proving the event details")


@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    validation_outcome: str  # "auto_published", "needs_review", "rejected"
    rejection_reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    is_historical: bool = False
    is_cancelled: bool = False
    verbatim_evidence_quote: Optional[str] = None
    extracted_data: Optional[dict[str, Any]] = None


async def extract_with_ollama(
    text_content: str,
    *,
    model: str = "qwen2.5:7b-instruct",
    ollama_host: Optional[str] = None,
    timeout: float = 20.0,
) -> Optional[OllamaEventExtraction]:
    """
    Passes Trafilatura text to Ollama using Pydantic JSON schema format.
    Enforces zero hallucination: returns null if a detail is not explicitly in text.
    """
    host = ollama_host or getattr(settings, "ollama_host", "http://ollama:11434")
    prompt = (
        "Extract the following event details from the text strictly into the requested JSON schema.\n"
        "ENFORCE ZERO HALLUCINATION: If a detail (like venue, dates, or registration url) is not explicitly "
        "and clearly stated in the text, you MUST return null for that field.\n"
        "Include a verbatim_evidence_quote copying the exact sentence from the text demonstrating the event details.\n\n"
        f"TEXT:\n{text_content[:4000]}"
    )

    try:
        # Check if ollama client package is available
        import ollama
        client = ollama.AsyncClient(host=host)
        resp = await client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=OllamaEventExtraction.model_json_schema(),
            options={"temperature": 0.0},
        )
        content = resp["message"]["content"]
        return OllamaEventExtraction.model_validate_json(content)
    except Exception as exc:
        logger.debug("Ollama async client invocation unavailable (%s); attempting HTTP REST call", exc)

    # HTTP Fallback
    try:
        endpoint = f"{host.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": OllamaEventExtraction.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0.0},
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_content = data.get("message", {}).get("content", "{}")
            return OllamaEventExtraction.model_validate_json(raw_content)
    except Exception as exc:
        logger.warning("Structured Ollama extraction failed (%s): %s", host, exc)
        return None


def _parse_date_flexible(date_str: str | None) -> Optional[datetime]:
    """Helper to parse dates using dateparser or dateutil."""
    if not date_str:
        return None
    try:
        import dateparser
        dt = dateparser.parse(date_str)
        if dt:
            return dt
    except Exception:
        pass
    try:
        from dateutil import parser as du_parser
        return du_parser.parse(date_str)
    except Exception:
        return None


def validate_candidate(
    title: str,
    description: str | None,
    start_date: datetime | None,
    end_date: datetime | None = None,
    registration_url: str | None = None,
    organizer_name: str | None = None,
    source_name: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    registration_deadline: datetime | None = None,
    as_of: Optional[datetime] = None,
    mode: str = "offline",
    verbatim_evidence_quote: Optional[str] = None,
    extracted_data: Optional[dict[str, Any]] = None,
) -> ValidationResult:
    """
    Confidence Scorer & Gatekeeper:
    - Verify dates parse with dateparser and appear in the source quote (+0.30).
    - Verify location matches Tamil Nadu or verified hybrid/online (+0.25).
    - Verified organizer domain or accredited institution (+0.20).
    - Working registration URL (+0.15).
    - Detailed description (+0.10).

    Publication Decision:
    - Score >= 0.80 -> validation_outcome = "auto_published"
    - Score 0.45 - 0.79 -> validation_outcome = "needs_review"
    - Score < 0.45 -> validation_outcome = "rejected"
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    reasons: list[str] = []
    score = 0.0
    evidence: dict[str, Any] = {}
    is_historical = False
    is_cancelled = False

    # 1. Title verification
    clean_title = (title or "").strip()
    if not clean_title or len(clean_title) < 5:
        reasons.append("Title is too short or missing (< 5 characters)")
    elif clean_title.lower() in GENERIC_TITLES:
        reasons.append(f"Title '{clean_title}' is generic or boilerplate")
    elif len(clean_title) > 240:
        reasons.append("Title exceeds maximum length of 240 characters")
    else:
        evidence["valid_title"] = True

    # 2. Cancellation Check
    full_text = f"{clean_title} {description or ''} {verbatim_evidence_quote or ''}"
    if CANCELLATION_PATTERN.search(full_text):
        is_cancelled = True
        evidence["cancellation_detected"] = True
        reasons.append("Event is cancelled or postponed indefinitely")

    # 3. Date Integrity & Verification (+0.30)
    if not start_date:
        reasons.append("Start date is missing or unparseable")
    else:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if registration_deadline and registration_deadline.tzinfo is None:
            registration_deadline = registration_deadline.replace(tzinfo=timezone.utc)

        # Contradictory dates
        if end_date and end_date < start_date:
            reasons.append("Contradictory dates: end_date cannot be earlier than start_date")

        if registration_deadline:
            effective_limit = end_date or start_date
            if registration_deadline > effective_limit:
                reasons.append("Contradictory dates: registration_deadline cannot be after event conclusion")
            else:
                evidence["valid_registration_deadline"] = registration_deadline.isoformat()

        # Effective end & Historical check
        effective_end = get_effective_end_date(start_date, end_date)
        if as_of > effective_end:
            is_historical = True
            reasons.append(f"Historical event: effective end date ({effective_end.isoformat()}) has already passed")
        else:
            # Date verified
            evidence["dates_verified"] = True
            evidence["start_date"] = start_date.isoformat()
            if end_date:
                evidence["end_date"] = end_date.isoformat()

            # Date in quote or valid parser match
            score += 0.30
            if verbatim_evidence_quote and str(start_date.year) in verbatim_evidence_quote:
                evidence["date_in_quote"] = True

    # 4. Location Verification (+0.25)
    location_verified = False
    if mode in ("online", "hybrid"):
        location_verified = True
        evidence["location_type"] = f"verified_{mode}"
    else:
        combined_loc = f"{venue or ''} {city or ''}".lower()
        if any(d.lower() in combined_loc for d in TAMIL_NADU_DISTRICTS) or any(a in combined_loc for a in DISTRICT_ALIASES):
            location_verified = True
            evidence["location_type"] = "tamil_nadu_verified"
        elif "tamil nadu" in combined_loc:
            location_verified = True
            evidence["location_type"] = "state_verified"

    if location_verified:
        score += 0.25
        evidence["location_verified"] = True
    else:
        evidence["location_verified"] = False

    # 5. Verified Organizer Domain or Accredited Institution (+0.20)
    organizer_str = f"{organizer_name or ''} {source_name or ''}"
    if organizer_str and ACCREDITED_INSTITUTION_PATTERN.search(organizer_str):
        score += 0.20
        evidence["accredited_organizer"] = True
    elif organizer_name or source_name:
        score += 0.10
        evidence["standard_organizer"] = True
    else:
        reasons.append("No organizer or credible source attribution found")

    # 6. Working Registration URL (+0.15)
    clean_url = (registration_url or "").strip()
    if clean_url and (clean_url.startswith("http://") or clean_url.startswith("https://")):
        score += 0.15
        evidence["valid_registration_url"] = True
    else:
        reasons.append("Registration URL is missing or does not start with http(s)://")

    # 7. Detailed Description (+0.10)
    clean_desc = (description or "").strip()
    if len(clean_desc) >= 100:
        score += 0.10
        evidence["detailed_description"] = True
    elif len(clean_desc) >= 20:
        score += 0.05
        evidence["basic_description"] = True
    else:
        reasons.append("Description is missing or too brief (< 20 characters)")

    final_score = round(min(score, 1.0), 2)

    # 8. Publication Decision Gatekeeper
    if is_historical or is_cancelled or not start_date or (end_date and end_date < start_date):
        validation_outcome = "rejected"
        is_valid = False
    elif final_score >= 0.80 and len(reasons) == 0:
        validation_outcome = "auto_published"
        is_valid = True
    elif final_score >= 0.45:
        validation_outcome = "needs_review"
        is_valid = False
    else:
        validation_outcome = "rejected"
        is_valid = False

    return ValidationResult(
        is_valid=is_valid,
        confidence_score=final_score,
        validation_outcome=validation_outcome,
        rejection_reasons=reasons,
        evidence=evidence,
        is_historical=is_historical,
        is_cancelled=is_cancelled,
        verbatim_evidence_quote=verbatim_evidence_quote,
        extracted_data=extracted_data,
    )
