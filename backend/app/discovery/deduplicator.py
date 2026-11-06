import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Event, EventSource


def _normalize_title_for_comparison(title: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(cleaned.split())


def _token_jaccard_similarity(str1: str, str2: str) -> float:
    tokens1 = set(str1.split())
    tokens2 = set(str2.split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


def find_matching_event(
    db: Session,
    *,
    source_id: int,
    canonical_url: str,
    canonical_registration_url: str | None,
    external_event_id: str | None,
    title: str,
    start_date: datetime,
    organizer_name: str | None = None,
    city: str | None = None,
) -> Optional[Event]:
    """
    Finds existing event matching by:
    1. Exact source + external event ID.
    2. Exact canonical URL in EventSource.
    3. Exact registration URL in Event.
    4. Exact date + high title/organizer similarity.
    """
    # 1. Check EventSource by source_id + external_event_id
    if external_event_id:
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

    # 2. Check EventSource by canonical URL
    if canonical_url:
        stmt = (
            select(Event)
            .join(EventSource, Event.id == EventSource.event_id)
            .where(EventSource.canonical_url == canonical_url)
        )
        matched = db.scalar(stmt)
        if matched:
            return matched

    # 3. Check Event by registration_url
    if canonical_registration_url:
        stmt = select(Event).where(
            or_(
                Event.registration_url == canonical_registration_url,
                Event.ticket_url == canonical_registration_url,
                Event.official_website == canonical_url,
            )
        )
        matched = db.scalar(stmt)
        if matched:
            return matched

    # 4. Check Date + Title Similarity
    norm_candidate_title = _normalize_title_for_comparison(title)

    # Window of +/- 24 hours around start_date
    start_window = start_date - timedelta(hours=24)
    end_window = start_date + timedelta(hours=24)

    candidate_events = db.scalars(
        select(Event).where(
            Event.start_date >= start_window,
            Event.start_date <= end_window,
        )
    ).all()

    for candidate in candidate_events:
        norm_existing_title = _normalize_title_for_comparison(candidate.title)
        # Exact title match on the same day
        if norm_candidate_title == norm_existing_title:
            return candidate

        # High Jaccard similarity (>= 0.85) on titles with at least 3 words
        words = norm_candidate_title.split()
        if len(words) >= 3:
            similarity = _token_jaccard_similarity(norm_candidate_title, norm_existing_title)
            if similarity >= 0.85:
                # Also check organizer or city overlap if available
                if organizer_name and candidate.organizer_name:
                    norm_org1 = _normalize_title_for_comparison(organizer_name)
                    norm_org2 = _normalize_title_for_comparison(candidate.organizer_name)
                    if norm_org1 in norm_org2 or norm_org2 in norm_org1:
                        return candidate
                elif city and candidate.city and city.lower() == candidate.city.lower():
                    return candidate

    return None

