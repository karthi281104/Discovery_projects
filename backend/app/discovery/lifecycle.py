import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Event

logger = logging.getLogger(__name__)

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
DEFAULT_DURATION_HOURS = 4


def is_date_only_timestamp(dt: datetime) -> bool:
    """
    Checks if a datetime falls exactly at midnight in Asia/Kolkata (or UTC),
    which is typical of date-only inputs without explicit time components.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kolkata_dt = dt.astimezone(KOLKATA_TZ)
    return kolkata_dt.hour == 0 and kolkata_dt.minute == 0 and kolkata_dt.second == 0 and kolkata_dt.microsecond == 0


def get_effective_end_date(
    start_date: datetime,
    end_date: Optional[datetime],
    *,
    is_date_only: bool = False,
    default_duration_hours: int = DEFAULT_DURATION_HOURS,
) -> datetime:
    """
    Calculates the effective end time in UTC for an event.

    Rules:
    - If explicit end_date exists:
      - If it is date-only (or marked date-only), lasts through the entire local calendar day (23:59:59.999999 IST).
      - If timed, uses the exact end_date.
    - If end_date is missing:
      - If date-only, lasts through the entire local calendar day of start_date (23:59:59.999999 IST).
      - If timed one-day event, applies a default duration policy (start_date + default_duration_hours).
    """
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    if end_date is not None:
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        # Check if end_date represents a date-only boundary
        if is_date_only or is_date_only_timestamp(end_date):
            kolkata_end = end_date.astimezone(KOLKATA_TZ)
            end_of_day_kolkata = kolkata_end.replace(hour=23, minute=59, second=59, microsecond=999999)
            return end_of_day_kolkata.astimezone(timezone.utc)
        return end_date

    # end_date is None
    if is_date_only or is_date_only_timestamp(start_date):
        kolkata_start = start_date.astimezone(KOLKATA_TZ)
        end_of_day_kolkata = kolkata_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        return end_of_day_kolkata.astimezone(timezone.utc)

    # Timed one-day event without end_date: apply default duration policy
    return start_date + timedelta(hours=default_duration_hours)


def classify_event_lifecycle(
    event: Event,
    as_of: Optional[datetime] = None,
    default_duration_hours: int = DEFAULT_DURATION_HOURS,
) -> str:
    """
    Classifies an event into one of:
    - 'cancelled': Event has been cancelled. Never expired or marked active.
    - 'expired': Event past its effective end and has been transitioned to expired.
    - 'past': Event past its effective end time but not yet transitioned to expired.
    - 'ongoing': Event has started and is currently ongoing before its effective end time.
    - 'upcoming': Event has not yet started.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    if event.status == "cancelled":
        return "cancelled"

    start = event.start_date or event.starts_at
    if start is None:
        return "expired" if event.status == "expired" else "past"

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    # Check tags or attributes for date-only indicator
    is_date_only = False
    if isinstance(event.tags, list) and "date_only" in event.tags:
        is_date_only = True
    elif is_date_only_timestamp(start):
        is_date_only = True

    effective_end = get_effective_end_date(
        start,
        event.end_date or event.ends_at,
        is_date_only=is_date_only,
        default_duration_hours=default_duration_hours,
    )

    if as_of < start:
        return "upcoming"
    elif start <= as_of <= effective_end:
        return "ongoing"
    else:
        # Effective end has passed
        return "expired" if event.status == "expired" else "past"


def expire_past_events(
    db: Session,
    as_of: Optional[datetime] = None,
    default_duration_hours: int = DEFAULT_DURATION_HOURS,
) -> int:
    """
    Centralized event expiry engine.
    Finds active published events whose effective end time has passed as of `as_of`,
    and safely marks them status='expired' and is_published=False.

    Idempotent and never re-expires cancelled events.
    Logs transition counts and reasons.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    # Select all published events (exclude cancelled and already expired)
    published_events = db.scalars(
        select(Event).where(
            Event.status == "published",
            Event.is_published.is_(True),
        )
    ).all()

    expired_count = 0
    for event in published_events:
        lifecycle = classify_event_lifecycle(event, as_of=as_of, default_duration_hours=default_duration_hours)
        if lifecycle in ("past", "expired"):
            event.status = "expired"
            event.is_published = False
            expired_count += 1
            logger.info(
                "Event #%d '%s' transitioned to expired (start=%s, end=%s, effective_end_passed=True)",
                event.id,
                event.title,
                event.start_date,
                event.end_date,
            )

    if expired_count > 0:
        db.commit()
        logger.info("Lifecycle sweep expired %d events at as_of=%s", expired_count, as_of.isoformat())

    return expired_count


def reconcile_event_lifecycle(
    db: Session,
    *,
    dry_run: bool = True,
    preserve_manual_cancellations: bool = True,
    as_of: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Performs a non-destructive or applied lifecycle reconciliation across all events in database.

    Returns:
    - total_events: int
    - proposed_corrections: list of dicts with event details and reason
    - applied: bool
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    all_events = db.scalars(select(Event).order_by(Event.id)).all()
    corrections = []
    applied_count = 0

    for ev in all_events:
        # Preserve manual cancellations
        if preserve_manual_cancellations and ev.status == "cancelled":
            continue

        start = ev.start_date or ev.starts_at
        if not start:
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        is_date_only = "date_only" in (ev.tags or []) or is_date_only_timestamp(start)
        effective_end = get_effective_end_date(
            start,
            ev.end_date or ev.ends_at,
            is_date_only=is_date_only,
        )

        current_status = ev.status
        current_published = ev.is_published

        # Determine target lifecycle status
        if as_of < start:
            target_status = "published"
            target_published = True
            reason = "Future event currently within valid opportunity window"
        elif start <= as_of <= effective_end:
            target_status = "published"
            target_published = True
            reason = "Ongoing event currently within active duration"
        else:
            target_status = "expired"
            target_published = False
            reason = f"Event ended on {effective_end.isoformat()}"

        needs_change = (current_status != target_status) or (current_published != target_published)

        # Do not resurrect drafts unless specifically expired by mistake
        if current_status == "draft":
            continue

        if needs_change:
            correction = {
                "event_id": ev.id,
                "title": ev.title,
                "old_status": current_status,
                "old_is_published": current_published,
                "new_status": target_status,
                "new_is_published": target_published,
                "start_date": ev.start_date.isoformat() if ev.start_date else None,
                "end_date": ev.end_date.isoformat() if ev.end_date else None,
                "effective_end": effective_end.isoformat(),
                "reason": reason,
            }
            corrections.append(correction)

            if not dry_run:
                ev.status = target_status
                ev.is_published = target_published
                applied_count += 1

    if not dry_run and applied_count > 0:
        db.commit()
        logger.info("Applied lifecycle reconciliation to %d events", applied_count)

    return {
        "total_events": len(all_events),
        "corrections_count": len(corrections),
        "applied": not dry_run,
        "corrections": corrections,
    }


def compute_database_diagnostics(db: Session, as_of: Optional[datetime] = None) -> dict[str, Any]:
    """
    Computes system-wide event diagnostic counts as required by Section 13:
    - Total events
    - Published events
    - Expired events
    - Cancelled events
    - Future events
    - Ongoing events
    - Past events still published
    - Events missing end_date
    - Events with end_date earlier than start_date
    - Events with registration_deadline after start_date
    - Events with suspicious or inconsistent timezone data
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    all_events = db.scalars(select(Event).order_by(Event.id)).all()

    total = len(all_events)
    published = 0
    expired = 0
    cancelled = 0
    future = 0
    ongoing = 0
    past_still_published = 0
    missing_end_date = 0
    end_before_start = 0
    deadline_after_start = 0
    inconsistent_timezone = 0

    for ev in all_events:
        if ev.status == "published":
            published += 1
        elif ev.status == "expired":
            expired += 1
        elif ev.status == "cancelled":
            cancelled += 1

        start = ev.start_date or ev.starts_at
        end = ev.end_date or ev.ends_at

        if start is not None and start.tzinfo is None:
            inconsistent_timezone += 1
        elif end is not None and end.tzinfo is None:
            inconsistent_timezone += 1

        if start is not None:
            start_utc = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            end_utc = end if (end and end.tzinfo) else (end.replace(tzinfo=timezone.utc) if end else None)

            is_date_only = "date_only" in (ev.tags or []) or is_date_only_timestamp(start_utc)
            effective_end = get_effective_end_date(start_utc, end_utc, is_date_only=is_date_only)

            if as_of < start_utc:
                future += 1
            elif start_utc <= as_of <= effective_end:
                ongoing += 1

            if ev.status == "published" and as_of > effective_end:
                past_still_published += 1

        if end is None:
            missing_end_date += 1
        elif start is not None and end < start:
            end_before_start += 1

        if ev.registration_deadline is not None and start is not None:
            reg = ev.registration_deadline
            if reg.tzinfo is None:
                reg = reg.replace(tzinfo=timezone.utc)
            start_u = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            if reg > start_u:
                deadline_after_start += 1

    return {
        "total_events": total,
        "published_events": published,
        "expired_events": expired,
        "cancelled_events": cancelled,
        "future_events": future,
        "ongoing_events": ongoing,
        "past_events_still_published": past_still_published,
        "events_missing_end_date": missing_end_date,
        "events_end_date_earlier_than_start": end_before_start,
        "events_registration_deadline_after_start": deadline_after_start,
        "events_inconsistent_timezone": inconsistent_timezone,
    }


def handle_duplicate_event_update(
    db: Session,
    existing_event: Event,
    *,
    new_source_url: str | None = None,
    new_start_date: Optional[datetime] = None,
    new_venue_name: Optional[str] = None,
    new_registration_url: Optional[str] = None,
    as_of: Optional[datetime] = None,
) -> bool:
    """
    Handles event changes when a duplicate is detected:
    1. Appends the new URL to additional_source_urls.
    2. Compares fields: start_date, venue_name (event.venue), registration_url.
    3. If any field changed, writes the field diff into update_history and updates the event record.
    Returns True if fields were changed, False if unchanged.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    # 1. Append the new URL to additional_source_urls
    if new_source_url:
        additional_urls = list(existing_event.additional_source_urls or [])
        if new_source_url != existing_event.original_source_url and new_source_url not in additional_urls:
            additional_urls.append(new_source_url)
            existing_event.additional_source_urls = additional_urls

    # 2. Compare fields: (start_date, venue_name, registration_url)
    changes: dict[str, dict[str, Any]] = {}

    if new_start_date is not None:
        current_start = existing_event.start_date
        if current_start is not None and current_start.tzinfo is None:
            current_start = current_start.replace(tzinfo=timezone.utc)
        target_start = new_start_date if new_start_date.tzinfo else new_start_date.replace(tzinfo=timezone.utc)

        if current_start is None or current_start != target_start:
            changes["start_date"] = {
                "old": current_start.isoformat() if current_start else None,
                "new": target_start.isoformat(),
            }

    if new_venue_name is not None and new_venue_name.strip():
        current_venue = (existing_event.venue or "").strip()
        target_venue = new_venue_name.strip()
        if current_venue != target_venue:
            changes["venue_name"] = {
                "old": existing_event.venue,
                "new": target_venue,
            }

    if new_registration_url is not None and new_registration_url.strip():
        current_reg = (existing_event.registration_url or "").strip()
        target_reg = new_registration_url.strip()
        if current_reg != target_reg:
            changes["registration_url"] = {
                "old": existing_event.registration_url,
                "new": target_reg,
            }

    # 3. If any field changed, write field diff into update_history and update event record
    if changes:
        history = list(existing_event.update_history or [])
        for f_name, f_vals in changes.items():
            diff_entry = {
                "timestamp": as_of.isoformat(),
                "source_url": new_source_url or existing_event.original_source_url,
                "field": f_name,
                "old_value": f_vals["old"],
                "new_value": f_vals["new"],
                "changes": changes,
            }
            history.append(diff_entry)
        existing_event.update_history = history

        # Update event record
        if "start_date" in changes:
            target_start = new_start_date if new_start_date.tzinfo else new_start_date.replace(tzinfo=timezone.utc)
            existing_event.start_date = target_start
            existing_event.starts_at = target_start

        if "venue_name" in changes:
            existing_event.venue = new_venue_name.strip()

        if "registration_url" in changes:
            existing_event.registration_url = new_registration_url.strip()
            existing_event.ticket_url = new_registration_url.strip()

        existing_event.updated_at = as_of
        return True

    return False


