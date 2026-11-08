"""Autonomous search agent discovering events via SearXNG with smart combinator and queue management."""
from dataclasses import dataclass
from datetime import datetime, timezone
import itertools
import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse
import uuid

import httpx
from sqlalchemy import Date, cast, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.discovery.fetcher import SafeFetcher
from app.discovery.normalizer import normalize_url
from app.models import (
    DiscoveredUrl,
    DiscoverySource,
    SearchCampaign,
    SearchQueryExecution,
    SearchResult,
)

logger = logging.getLogger(__name__)

# ==========================================
# Combinator Constants
# ==========================================

LOCATIONS = [
    "Chennai",
    "Coimbatore",
    "Madurai",
    "Tiruchirappalli",
    "Salem",
    "Tirunelveli",
    "Vellore",
    "Tamil Nadu",
]

CATEGORIES_EN = [
    "Hackathon",
    "Symposium",
    "Workshop",
    "Conference",
    "Cultural Fest",
    "Tech Meetup",
    "Exhibition",
    "Book Fair",
]

CATEGORIES_TA = [
    "கருத்தரங்கம்",
    "திருவிழா",
    "போட்டி",
    "நிகழ்ச்சி",
]

ORGANIZER_KEYWORDS = [
    "College",
    "University",
    "TNSI",
    "StartupTN",
    "Community",
]

TIME_MARKERS = [
    "upcoming",
    "2026",
    "registration",
]

NON_EVENT_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".webp", ".mp4", ".mp3", ".avi", ".docx", ".doc", ".xlsx",
    ".xls", ".csv", ".exe", ".dmg", ".pkg", ".apk", ".ico"
}

AUTH_WALL_PATTERNS = [
    r"/login\b", r"/signin\b", r"/sign-in\b", r"/signup\b", r"/sign-up\b",
    r"/auth\b", r"/account\b", r"/user/register\b", r"/wp-login\.php",
    r"/wp-admin", r"/cart\b", r"/checkout\b", r"/password\b",
    r"/privacy-policy\b", r"/terms-of-service\b"
]


@dataclass(frozen=True)
class QuerySpecification:
    query_text: str
    language: str
    category: Optional[str] = None
    location_target: Optional[str] = None


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    snippet: str
    score: float = 0.0


def is_valid_event_url(url: str | None) -> bool:
    """Filters out non-event binaries, assets, and auth walls."""
    if not url:
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    domain = parsed.netloc.lower()
    blocked_domains = ("youtube.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com")
    if any(domain.endswith(b) for b in blocked_domains):
        return False

    path_lower = parsed.path.lower()

    # Filter out non-event files
    for ext in NON_EVENT_EXTENSIONS:
        if path_lower.endswith(ext):
            return False

    # Filter out auth walls & non-event endpoints
    for pattern in AUTH_WALL_PATTERNS:
        if re.search(pattern, path_lower):
            return False

    return True


def generate_autonomous_queries(max_queries: int = 50) -> list[QuerySpecification]:
    """
    Autonomous Query Combinator:
    Combines locations, categories, languages, organizer keywords, and time markers.
    """
    specs: list[QuerySpecification] = []

    # 1. English: Region + Category + Time markers
    for cat in CATEGORIES_EN[:4]:
        query_str = f'"{cat}" "Tamil Nadu" 2026 registration'
        specs.append(QuerySpecification(query_str, language="en", category=cat, location_target="Tamil Nadu"))

    for loc, cat in itertools.product(LOCATIONS[:3], CATEGORIES_EN[:3]):
        query_str = f'"{cat}" "{loc}" 2026 registration'
        specs.append(QuerySpecification(query_str, language="en", category=cat, location_target=loc))

    # 2. Tamil: Specific event types & Tamil category terms
    for ta_term in CATEGORIES_TA:
        query_str = f"தமிழ்நாடு {ta_term} பதிவு 2026"
        specs.append(QuerySpecification(query_str, language="ta", category=ta_term, location_target="Tamil Nadu"))

    for loc, ta_term in itertools.product(LOCATIONS[:3], CATEGORIES_TA):
        query_str = f"{ta_term} {loc} 2026 நிகழ்வுகள்"
        specs.append(QuerySpecification(query_str, language="ta", category=ta_term, location_target=loc))

    # 3. Additional English: Location + Category + Time markers
    for loc, cat in itertools.product(LOCATIONS, CATEGORIES_EN):
        query_str = f'"{cat}" "{loc}" 2026 registration'
        specs.append(QuerySpecification(query_str, language="en", category=cat, location_target=loc))

    # 4. English: Organizer + Category + Location
    for org, cat, loc in itertools.product(ORGANIZER_KEYWORDS[:3], CATEGORIES_EN[:4], LOCATIONS[:4]):
        query_str = f"{org} {cat} {loc} 2026"
        specs.append(QuerySpecification(query_str, language="en", category=cat, location_target=loc))

    # Deduplicate while preserving order
    seen = set()
    unique_specs: list[QuerySpecification] = []
    for spec in specs:
        if spec.query_text not in seen:
            seen.add(spec.query_text)
            unique_specs.append(spec)
        if len(unique_specs) >= max_queries:
            break

    return unique_specs


def build_queries(
    *,
    region: str = "Tamil Nadu",
    categories: tuple[str, ...] = ("hackathon", "conference", "workshop", "symposium", "meetup"),
    languages: tuple[str, ...] = ("en", "ta"),
) -> list[str]:
    """Compatibility helper returning query strings."""
    specs = generate_autonomous_queries(max_queries=60)
    filtered = [
        s.query_text for s in specs
        if s.language in languages and (not region or s.location_target in (region, "Tamil Nadu") or region in s.query_text)
    ]
    if not filtered:
        filtered = [s.query_text for s in specs if s.language in languages]
    return list(dict.fromkeys(filtered))


async def search_searxng(
    base_url: str,
    query: str,
    *,
    page: int = 1,
    results: int = 10,
    timeout: float = 15.0,
) -> list[SearchHit]:
    """
    SearXNG API Client:
    Makes async request to SearXNG search API, canonicalizes URLs, and drops non-event targets.
    """
    endpoint = base_url.rstrip("/") + "/search"
    params = {
        "q": query,
        "format": "json",
        "pageno": page,
        "categories": "general",
    }
    hits: list[SearchHit] = []

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.get(
                endpoint,
                params=params,
                headers={"User-Agent": settings.discovery_user_agent},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("SearXNG search error for '%s' (endpoint %s): %s", query, endpoint, exc)
        return []

    for item in payload.get("results", [])[:results]:
        raw_url = item.get("url")
        if not is_valid_event_url(raw_url):
            continue

        canonical = normalize_url(raw_url)
        if not is_valid_event_url(canonical):
            continue

        title = str(item.get("title", ""))
        snippet = str(item.get("content", ""))
        score = float(item.get("score", 0.0) or 0.0)

        hits.append(SearchHit(url=canonical, title=title, snippet=snippet, score=score))

    return hits


def _source_name(url: str) -> str:
    host = urlparse(url).hostname or url
    return f"Autodiscovered: {host}"[:160]


def _classify_hit(hit: SearchHit, region: str) -> float:
    text = f"{hit.title} {hit.snippet}".lower()
    keywords = (
        "event", "register", "registration", "conference", "workshop",
        "hackathon", "symposium", "meetup", "fest", "exhibition"
    )
    score = hit.score
    if any(keyword in text for keyword in keywords):
        score += 0.25
    if region.lower() in text:
        score += 0.20
    return min(score, 1.0)


async def execute_autonomous_search(
    db: Session,
    *,
    base_url: Optional[str] = None,
    max_queries: int = 20,
    results_per_query: int = 10,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """
    Executes autonomous query combinator, queries SearXNG, logs search_query_executions,
    and inserts new candidate canonical URLs into discovered_urls queue.
    """
    target_url = base_url or settings.searxng_url or settings.discovery_search_url or "http://searxng:8080"
    specs = generate_autonomous_queries(max_queries=max_queries)
    today = datetime.now(timezone.utc).date()

    total_queries_run = 0
    total_results_found = 0
    total_new_urls = 0

    for spec in specs:
        now = datetime.now(timezone.utc)
        page_num = 1

        # Prevent duplicate searches within the same calendar day
        existing_run = db.scalar(
            select(SearchQueryExecution.id).where(
                SearchQueryExecution.query_text == spec.query_text,
                SearchQueryExecution.page_number == page_num,
                cast(SearchQueryExecution.executed_at, Date) == today,
            )
        )
        if existing_run:
            logger.debug("Search query already executed today, skipping: %s", spec.query_text)
            continue

        hits = await search_searxng(
            target_url,
            spec.query_text,
            page=page_num,
            results=results_per_query,
            timeout=timeout,
        )
        total_queries_run += 1
        total_results_found += len(hits)
        new_urls_in_query = 0

        for hit in hits:
            domain = urlparse(hit.url).netloc.lower()
            existing_url = db.scalar(
                select(DiscoveredUrl.id).where(DiscoveredUrl.canonical_url == hit.url)
            )
            if not existing_url:
                # Classify URL
                classification = "listing_hub" if any(k in hit.url for k in ("/events", "/calendar", "/feed")) else "event_page"
                discovered = DiscoveredUrl(
                    id=uuid.uuid4(),
                    raw_url=hit.url,
                    canonical_url=hit.url,
                    domain=domain,
                    classification=classification,
                    fetch_status="pending",
                    http_status=None,
                    discovered_at=now,
                )
                db.add(discovered)
                new_urls_in_query += 1
                total_new_urls += 1

        # Log query execution
        yield_score = (new_urls_in_query / len(hits)) if hits else 0.0
        log_entry = SearchQueryExecution(
            id=uuid.uuid4(),
            query_text=spec.query_text,
            language=spec.language,
            category=spec.category,
            location_target=spec.location_target,
            page_number=page_num,
            results_count=len(hits),
            new_urls_count=new_urls_in_query,
            yield_score=yield_score,
            executed_at=now,
        )
        db.add(log_entry)
        db.commit()

    return {
        "queries_executed": total_queries_run,
        "results_collected": total_results_found,
        "new_urls_queued": total_new_urls,
    }


async def run_search_campaign(
    db: Session,
    *,
    fetcher: SafeFetcher | None = None,
    region: str = "Tamil Nadu",
) -> SearchCampaign:
    """
    Autonomous search campaign integrating queue insertion, logging,
    and source discovery for backward compatibility with worker and admin API.
    """
    target_url = settings.searxng_url or settings.discovery_search_url or "http://searxng:8080"
    started_at = datetime.now(timezone.utc)
    campaign = SearchCampaign(started_at=started_at, status="running", region=region)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    if fetcher is None:
        fetcher = SafeFetcher()

    discovered_sources: dict[str, DiscoverySource] = {}

    try:
        # 1. Run autonomous search and queue URLs
        stats = await execute_autonomous_search(
            db,
            base_url=target_url,
            max_queries=settings.discovery_search_max_queries or 12,
            results_per_query=settings.discovery_search_results_per_query or 10,
            timeout=settings.discovery_request_timeout or 15.0,
        )
        campaign.queries_executed = stats["queries_executed"]
        campaign.results_collected = stats["results_collected"]

        # 2. Pick top discovered URLs for immediate source conversion
        pending_urls = db.scalars(
            select(DiscoveredUrl)
            .where(DiscoveredUrl.fetch_status == "pending")
            .order_by(DiscoveredUrl.discovered_at.desc())
            .limit(10)
        ).all()

        for d_url in pending_urls:
            canonical = d_url.canonical_url
            source = db.scalar(select(DiscoverySource).where(DiscoverySource.base_url == canonical))
            if source is None:
                source = DiscoverySource(
                    name=_source_name(canonical),
                    base_url=canonical,
                    source_type="auto",
                    region=region,
                    crawl_interval=settings.discovery_search_interval_minutes or 360,
                    request_config={"autodiscovered": True},
                )
                db.add(source)
                db.flush()
                campaign.sources_discovered += 1
            discovered_sources[canonical] = source
            d_url.fetch_status = "fetched"
            d_url.fetched_at = datetime.now(timezone.utc)
            db.commit()

        # Ingest from newly discovered sources
        from app.discovery.service import run_discovery_for_source
        for source in discovered_sources.values():
            try:
                await run_discovery_for_source(db, source.id, fetcher)
            except Exception as e:
                logger.debug("Source discovery run skipped for %s: %s", source.base_url, e)

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


BLOCKED_SEARCH_DOMAINS = (
    "youtube.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com"
)
IGNORED_SEARCH_EXTENSIONS = (
    ".pdf", ".docx", ".xlsx", ".zip", ".jpg", ".png", ".svg"
)


class AutonomousSearchEngine:
    """Autonomous search engine interface providing SearXNG querying, filtering, and canonicalization."""

    def __init__(self, base_url: Optional[str] = None):
        configured = (
            base_url
            or getattr(settings, "searxng_base_url", None)
            or getattr(settings, "searxng_url", None)
            or "http://localhost:8080"
        )
        self.base_url = configured.rstrip("/")

    async def execute_raw_search(self, query_text: str, page: int = 1) -> list[dict[str, Any]]:
        params = {
            "q": query_text,
            "format": "json",
            "categories": "general",
            "pageno": page,
        }
        endpoints_to_try = [f"{self.base_url}/search"]
        if "searxng:8080" in self.base_url:
            endpoints_to_try.append("http://localhost:8080/search")
        elif "localhost:8080" in self.base_url:
            endpoints_to_try.append("http://searxng:8080/search")

        for endpoint in endpoints_to_try:
            try:
                async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                    response = await client.get(
                        endpoint,
                        params=params,
                        headers={"User-Agent": getattr(settings, "discovery_user_agent", "TamilEventDiscoveryBot/1.0")},
                    )
                    if response.status_code != 200:
                        logger.error("SearXNG error %s from %s: %s", response.status_code, endpoint, response.text)
                        continue

                    data = response.json()
                    raw_results = data.get("results", [])
                    logger.info("SearXNG query='%s' returned %d results", query_text, len(raw_results))
                    return raw_results
            except Exception as e:
                logger.debug("SearXNG endpoint %s failed for query '%s': %s", endpoint, query_text, e)
                continue

        logger.error("SearXNG connection error for query '%s'", query_text)
        return []

    def filter_and_canonicalize(
        self,
        raw_results: list[dict[str, Any]],
        existing_urls: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        clean_candidates = []
        existing = existing_urls or set()

        for item in raw_results:
            url = (item.get("url") or "").strip()
            if not url or url in existing:
                continue

            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if any(domain.endswith(b) for b in BLOCKED_SEARCH_DOMAINS):
                continue

            if parsed.path.lower().endswith(IGNORED_SEARCH_EXTENSIONS):
                continue

            clean_candidates.append({
                "url": url,
                "domain": domain,
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "snippet": item.get("content", ""),
                "score": float(item.get("score", 0.0) or 0.0),
            })

        return clean_candidates

    @classmethod
    async def query_searxng(
        cls_or_self,
        query_text: str = "",
        page: int = 1,
        base_url: Optional[str] = None,
        query: str = "",
        **kwargs,
    ) -> list[dict[str, Any]]:
        target_query = query_text or query or kwargs.get("q", "")
        if isinstance(cls_or_self, AutonomousSearchEngine):
            engine = cls_or_self
            if base_url:
                engine.base_url = base_url.rstrip("/")
        else:
            engine = cls_or_self(base_url=base_url)

        raw_results = await engine.execute_raw_search(target_query, page=page)
        return engine.filter_and_canonicalize(raw_results)

