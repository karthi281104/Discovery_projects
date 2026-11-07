import logging
import re
from typing import Any
import feedparser

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.models import DiscoverySource

logger = logging.getLogger(__name__)

EVENT_DATE_PATTERNS = [
    # "13th & 14th November 2026" or "13th - 14th November 2026" or "13 to 14 November 2026"
    re.compile(r"(\d{1,2}(?:st|nd|rd|th)?\s*(?:&|-|to)\s*\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})", re.IGNORECASE),
    # "13th November 2026" or "13 November 2026"
    re.compile(r"(\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}\b)", re.IGNORECASE),
    # "November 13, 2026"
    re.compile(r"(\b[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b)", re.IGNORECASE),
    # "2026-11-13"
    re.compile(r"(\b\d{4}-\d{2}-\d{2}\b)"),
    # "13/11/2026" or "13-11-2026"
    re.compile(r"(\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b)"),
]


def extract_date_from_text(text: str) -> str | None:
    """Extracts an event date string mentioned in title or summary text."""
    if not text:
        return None
    for pattern in EVENT_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


class RSSConnector(BaseConnector):
    """Extracts event candidates from RSS and Atom XML feeds without inventing dates."""

    async def extract_candidates(
        self,
        source: DiscoverySource,
        fetcher: Any,
    ) -> list[RawCandidate]:
        response = await fetcher.fetch(source.base_url)
        content = response.text

        feed = feedparser.parse(content)
        if feed.bozo and not feed.entries:
            logger.warning("Feedparser error parsing %s: %s", source.base_url, feed.bozo_exception)
            return []

        candidates: list[RawCandidate] = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            summary = entry.get("summary") or entry.get("description") or ""
            if isinstance(summary, dict):
                summary = summary.get("value", "")

            # Look for explicit event dates in tags/extensions used by common
            # RSS event plugins and feeds.
            start_date_str = (
                entry.get("ev_startdate")
                or entry.get("start_date")
                or entry.get("event_start")
                or entry.get("startDate")
                or entry.get("dtstart")
                or entry.get("date")
            )
            end_date_str = (
                entry.get("ev_enddate")
                or entry.get("end_date")
                or entry.get("event_end")
                or entry.get("endDate")
                or entry.get("dtend")
            )

            # If no explicit event date tag, attempt extraction from title or summary text
            if not start_date_str:
                extracted = extract_date_from_text(title) or extract_date_from_text(summary)
                if extracted:
                    start_date_str = extracted

            # Some event feeds expose only Atom's published timestamp. Keep this
            # opt-out because it is the only usable date for those feeds, while
            # allowing article/news feeds to disable the fallback explicitly.
            source_config = source.request_config or {}
            if not start_date_str and source_config.get("use_published_as_event_date", True):
                start_date_str = entry.get("published") or entry.get("updated")

            organizer = entry.get("author") or entry.get("author_detail", {}).get("name")
            tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

            # External ID
            ext_id = str(entry.get("id") or link)

            candidates.append(
                RawCandidate(
                    title=title,
                    url=link,
                    description=summary,
                    short_description=summary[:200] if summary else None,
                    start_date_str=str(start_date_str) if start_date_str else None,
                    end_date_str=str(end_date_str) if end_date_str else None,
                    organizer=organizer,
                    registration_url=link,
                    tags=tags,
                    external_id=ext_id,
                    raw_payload=dict(entry),
                )
            )

        return candidates
