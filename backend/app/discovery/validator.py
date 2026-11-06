from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

GENERIC_TITLES = {
    "home", "events", "upcoming events", "past events", "untitled",
    "contact us", "about us", "privacy policy", "terms of service",
    "404 not found", "advertisement", "subscribe", "read more",
    "news", "press release", "blog", "articles", "welcome"
}


@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    rejection_reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def validate_candidate(
    title: str,
    description: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    registration_url: str | None,
    organizer_name: str | None,
    source_name: str | None = None,
    venue: str | None = None,
    city: str | None = None,
) -> ValidationResult:
    """
    Evaluates candidate quality, evidence, and completeness.
    Returns whether the candidate is valid for automatic publishing.
    """
    reasons: list[str] = []
    score = 0.0
    evidence: dict[str, Any] = {}

    # 1. Title verification
    clean_title = (title or "").strip()
    if not clean_title or len(clean_title) < 5:
        reasons.append("Title is too short or missing (< 5 characters)")
    elif clean_title.lower() in GENERIC_TITLES:
        reasons.append(f"Title '{clean_title}' is generic or boilerplate")
    elif len(clean_title) > 240:
        reasons.append("Title exceeds maximum length of 240 characters")
    else:
        score += 0.25
        evidence["valid_title"] = True

    # 2. Date verification
    if not start_date:
        reasons.append("Start date is missing or unparseable")
    else:
        now = datetime.now(timezone.utc)
        # Event shouldn't be older than 365 days
        days_diff = (now - start_date).days
        if days_diff > 365:
            reasons.append("Event date is more than 1 year in the past")
        else:
            score += 0.25
            evidence["valid_start_date"] = start_date.isoformat()

        if end_date and end_date < start_date:
            reasons.append("End date cannot be earlier than start date")

    # 3. Description verification
    clean_desc = (description or "").strip()
    if not clean_desc or len(clean_desc) < 15:
        reasons.append("Description is missing or too brief (< 15 characters)")
    else:
        score += 0.20
        evidence["has_description"] = True

    # 4. Registration / Event URL verification
    clean_url = (registration_url or "").strip()
    if not clean_url or not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        reasons.append("Registration/Event URL is missing or does not start with http(s)://")
    else:
        score += 0.15
        evidence["valid_url"] = True

    # 5. Organizer or Credible Source
    effective_organizer = (organizer_name or "").strip() or (source_name or "").strip()
    if not effective_organizer:
        reasons.append("No organizer or credible source attribution found")
    else:
        score += 0.10
        evidence["organizer"] = effective_organizer

    # 6. Location / Venue bonus
    if venue or city:
        score += 0.05
        evidence["has_location"] = True

    is_valid = len(reasons) == 0 and score >= 0.70
    return ValidationResult(
        is_valid=is_valid,
        confidence_score=round(score, 2),
        rejection_reasons=reasons,
        evidence=evidence,
    )

