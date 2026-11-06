import logging
from typing import Any
import feedparser

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.models import DiscoverySource

logger = logging.getLogger(__name__)


class RSSConnector(BaseConnector):
    """Extracts event candidates from RSS and Atom XML feeds."""

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

            # Look for explicit event dates or fallback to published/updated
            start_date_str = (
                entry.get("ev_startdate")
                or entry.get("start_date")
                or entry.get("published")
                or entry.get("updated")
            )
            end_date_str = entry.get("ev_enddate") or entry.get("end_date")

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

