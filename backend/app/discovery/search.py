"""Compliant autonomous source discovery through a configured SearXNG instance."""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.discovery.fetcher import SafeFetcher
from app.discovery.normalizer import normalize_url
from app.models import DiscoverySource, SearchCampaign, SearchResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    snippet: str
    score: float


def build_queries(
    *,
    region: str = "Tamil Nadu",
    categories: tuple[str, ...] = ("hackathon", "conference", "workshop", "symposium", "meetup"),
    languages: tuple[str, ...] = ("en", "ta"),
) -> list[str]:
    queries: list[str] = []
    for category in categories:
        queries.append(f'"{category}" events "{region}" 2026')
        queries.append(f"{category} registration {region} event")
    if "ta" in languages:
        queries.append(f"தமிழ்நாடு {region} நிகழ்வுகள் பதிவு")
    return list(dict.fromkeys(queries))


def _classify_hit(hit: SearchHit, region: str) -> float:
    text = f"{hit.title} {hit.snippet}".lower()
    keywords = ("event", "register", "registration", "conference", "workshop", "hackathon", "symposium", "meetup")
    score = hit.score
    if any(keyword in text for keyword in keywords):
        score += 0.25
    if region.lower() in text:
        score += 0.2
    return min(score, 1.0)


async def search_searxng(
    base_url: str,
    query: str,
    *,
    results: int,
    timeout: float,
) -> list[SearchHit]:
    endpoint = base_url.rstrip("/") + "/search"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.get(
            endpoint,
            params={"q": query, "format": "json", "categories": "general", "language": "en"},
            headers={"User-Agent": settings.discovery_user_agent},
        )
        response.raise_for_status()
        payload = response.json()
    hits: list[SearchHit] = []
    for item in payload.get("results", [])[:results]:
        url = normalize_url(item.get("url"))
        if not url or urlparse(url).scheme not in {"http", "https"}:
            continue
        hits.append(SearchHit(url, str(item.get("title", "")), str(item.get("content", "")), 0.0))
    return hits


def _source_name(url: str) -> str:
    host = urlparse(url).hostname or url
    return f"Autodiscovered: {host}"[:160]


async def run_search_campaign(
    db: Session,
    *,
    fetcher: SafeFetcher | None = None,
    region: str = "Tamil Nadu",
) -> SearchCampaign:
    if not settings.discovery_search_url:
        raise RuntimeError("DISCOVERY_SEARCH_URL must configure a compliant SearXNG endpoint")
    started_at = datetime.now(timezone.utc)
    campaign = SearchCampaign(started_at=started_at, status="running", region=region)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    queries = build_queries(region=region, languages=tuple(settings.discovery_search_languages.split(",")))
    if fetcher is None:
        fetcher = SafeFetcher()
    discovered_sources: dict[str, DiscoverySource] = {}
    try:
        for query in queries[:settings.discovery_search_max_queries]:
            campaign.queries_executed += 1
            hits = await search_searxng(
                settings.discovery_search_url,
                query,
                results=settings.discovery_search_results_per_query,
                timeout=settings.discovery_request_timeout,
            )
            for hit in hits:
                campaign.results_collected += 1
                score = _classify_hit(hit, region)
                canonical = normalize_url(hit.url)
                result = SearchResult(
                    campaign_id=campaign.id,
                    query=query,
                    url=canonical,
                    title=hit.title[:500],
                    snippet=hit.snippet[:2000],
                    relevance_score=score,
                )
                db.add(result)
                if score < 0.45 or canonical in discovered_sources:
                    continue
                source = db.scalar(select(DiscoverySource).where(DiscoverySource.base_url == canonical))
                if source is None:
                    source = DiscoverySource(
                        name=_source_name(canonical),
                        base_url=canonical,
                        source_type="auto",
                        region=region,
                        crawl_interval=settings.discovery_search_interval_minutes,
                        request_config={"autodiscovered": True},
                    )
                    db.add(source)
                    db.flush()
                    campaign.sources_discovered += 1
                discovered_sources[canonical] = source
            db.commit()
        from app.discovery.service import run_discovery_for_source

        for source in discovered_sources.values():
            await run_discovery_for_source(db, source.id, fetcher)
        campaign.status = "success"
    except Exception as exc:
        campaign.status = "failed"
        campaign.error_message = str(exc)
        logger.exception("Autonomous search campaign #%s failed", campaign.id)
    finally:
        completed_at = datetime.now(timezone.utc)
        campaign.completed_at = completed_at
        campaign.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        db.commit()
        db.refresh(campaign)
    return campaign
