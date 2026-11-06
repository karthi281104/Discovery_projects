import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.discovery.lifecycle import get_effective_end_date

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


@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    rejection_reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    is_historical: bool = False
    is_cancelled: bool = False


def validate_candidate(
    title: str,
    description: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    registration_url: str | None = None,
    organizer_name: str | None = None,
    source_name: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    registration_deadline: datetime | None = None,
    as_of: Optional[datetime] = None,
) -> ValidationResult:
    """
    Evaluates candidate quality, date integrity, temporal validity, and completeness.

    Enforces:
    - Rejection of clearly historical events from active auto-publishing.
    - Acceptance of valid future and ongoing events.
    - Prevention of contradictory dates (end_date < start_date or registration_deadline > end_date).
    - Detection of cancellation announcements.
    - Distinction between registration deadline and event end date.
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
        score += 0.25
        evidence["valid_title"] = True

    # 2. Cancellation Check
    full_text = f"{clean_title} {description or ''}"
    if CANCELLATION_PATTERN.search(full_text):
        is_cancelled = True
        evidence["cancellation_detected"] = True

    # 3. Date verification & Temporal integrity
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

        # Distinguish registration deadline from event dates
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
            # Event is ongoing or future
            score += 0.25
            evidence["valid_dates"] = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat() if end_date else None,
                "effective_end": effective_end.isoformat(),
                "is_ongoing": (start_date <= as_of <= effective_end),
            }

    # 4. Description verification
    clean_desc = (description or "").strip()
    if not clean_desc or len(clean_desc) < 15:
        reasons.append("Description is missing or too brief (< 15 characters)")
    else:
        score += 0.20
        evidence["has_description"] = True

    # 5. Registration / Event URL verification
    clean_url = (registration_url or "").strip()
    if not clean_url or not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        reasons.append("Registration/Event URL is missing or does not start with http(s)://")
    else:
        score += 0.15
        evidence["valid_url"] = True

    # 6. Organizer or Credible Source
    effective_organizer = (organizer_name or "").strip() or (source_name or "").strip()
    if not effective_organizer:
        reasons.append("No organizer or credible source attribution found")
    else:
        score += 0.10
        evidence["organizer"] = effective_organizer

    # 7. Location / Venue bonus
    if venue or city:
        score += 0.05
        evidence["has_location"] = True

    is_valid = len(reasons) == 0 and score >= 0.70 and not is_historical
    return ValidationResult(
        is_valid=is_valid,
        confidence_score=round(score, 2),
        rejection_reasons=reasons,
        evidence=evidence,
        is_historical=is_historical,
        is_cancelled=is_cancelled,
    )
