import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Event, EventSource

try:
    from rapidfuzz import fuzz
except ImportError:
    # Fallback if rapidfuzz is not yet installed in local environment
    class _FuzzFallback:
        @staticmethod
        def token_sort_ratio(s1: str, s2: str) -> float:
            tokens1 = sorted(re.sub(r"[^\w\s]", "", (s1 or "").lower()).split())
            tokens2 = sorted(re.sub(r"[^\w\s]", "", (s2 or "").lower()).split())
            if not tokens1 or not tokens2:
                return 0.0
            t1 = " ".join(tokens1)
            t2 = " ".join(tokens2)
            if t1 == t2:
                return 100.0
            set1, set2 = set(tokens1), set(tokens2)
            jaccard = len(set1 & set2) / len(set1 | set2)
            return jaccard * 100.0

    fuzz = _FuzzFallback()


def normalize_title_for_comparison(title: str) -> str:
    """Normalizes title by removing punctuation, lowercasing, and normalizing whitespace."""
    cleaned = re.sub(r"[^\w\s]", "", (title or "").lower())
    return " ".join(cleaned.split())


def compute_event_content_hash(
    title: str,
    start_date: datetime | str | None,
    city: str | None = None,
) -> str:
    """
    Computes deterministic SHA256 content_hash of normalized title, start date, and city.
    Serves as the primary deduplication key.
    """
    norm_title = normalize_title_for_comparison(title)

    if isinstance(start_date, datetime):
        norm_date = start_date.strftime("%Y-%m-%d")
    elif isinstance(start_date, str) and start_date:
        norm_date = start_date.strip()[:10]
    else:
        norm_date = ""

    norm_city = (city or "").lower().strip()

    raw_key = f"{norm_title}|{norm_date}|{norm_city}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def find_matching_event(
    db: Session,
    *,
    source_id: int | None = None,
    canonical_url: str | None = None,
    canonical_registration_url: str | None = None,
    external_event_id: str | None = None,
    title: str,
    start_date: datetime,
    organizer_name: str | None = None,
    city: str | None = None,
) -> Optional[Event]:
    """
    Finds existing event matching by:
    1. Primary key: content_hash of normalized title, start date, and city.
    2. Exact source + external event ID.
    3. Exact canonical URL in EventSource or registration URL in Event.
    4. Fuzzy cross-source check: query database for existing events within +/- 2 days
       in the same city. Run rapidfuzz.fuzz.token_sort_ratio(candidate.title, existing.title).
       If >= 85%, treat as duplicate.
    """
    # 1. Primary key content_hash match
    content_hash = compute_event_content_hash(title, start_date, city)
    if content_hash:
        matched = db.scalar(select(Event).where(Event.content_hash == content_hash))
        if matched:
            return matched

    # 2. Check EventSource by source_id + external_event_id
    if source_id and external_event_id:
        stmt = (
            select(Event)
            .join(EventSource, Event.id == EventSource.event_id)
            .where(
                EventSource.source_id == source_id,
                EventSource.external_event_id == external_event_id,
            )
        )
        matched = db.scalar(stmt)
        if matched:
            return matched

    # 3. Check EventSource by canonical URL
    if canonical_url:
        stmt = (
            select(Event)
            .join(EventSource, Event.id == EventSource.event_id)
            .where(EventSource.canonical_url == canonical_url)
        )
        matched = db.scalar(stmt)
        if matched:
            return matched

    # Check Event by registration_url or official_website
    if canonical_registration_url:
        stmt = select(Event).where(
            or_(
                Event.registration_url == canonical_registration_url,
                Event.ticket_url == canonical_registration_url,
                Event.official_website == (canonical_url or ""),
            )
        )
        matched = db.scalar(stmt)
        if matched:
            return matched

    # 4. Fuzzy cross-source check: query database for existing events within +/- 2 days in the same city.
    # Run rapidfuzz.fuzz.token_sort_ratio(candidate.title, existing.title). If >= 85%, treat as duplicate.
    if start_date:
        start_window = start_date - timedelta(days=2)
        end_window = start_date + timedelta(days=2)

        query = select(Event).where(
            Event.start_date >= start_window,
            Event.start_date <= end_window,
        )
        if city and city.strip():
            query = query.where(func.lower(Event.city) == city.strip().lower())

        candidate_events = db.scalars(query).all()
        norm_candidate_title = normalize_title_for_comparison(title)

        for candidate in candidate_events:
            norm_existing_title = normalize_title_for_comparison(candidate.title)
            # Exact title match on the same day window
            if norm_candidate_title == norm_existing_title:
                return candidate

            # Fuzzy title similarity via rapidfuzz token_sort_ratio
            score = fuzz.token_sort_ratio(title, candidate.title)
            if score >= 85:
                return candidate

    return None
