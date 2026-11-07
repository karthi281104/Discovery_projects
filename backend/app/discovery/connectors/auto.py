import json
import logging
import re
from typing import Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.discovery.connectors.html import HTMLConnector
from app.discovery.connectors.jsonld import JsonLdConnector, _extract_items
from app.discovery.connectors.rss import RSSConnector, extract_date_from_text
from app.models import DiscoverySource

logger = logging.getLogger(__name__)


class AutoConnector(BaseConnector):
    """
    Structured dynamic extractor:
    1. Inspects JSON-LD (application/ld+json) for Schema.org Event -> routes to jsonld.py
    2. Inspects <link rel="alternate" type="application/rss+xml"> -> routes to rss.py
    3. Fallback: Runs trafilatura.extract(html, include_links=True) for clean boilerplate-free text
    4. Fallback: Semantic HTML extraction
    """

    async def extract_candidates(self, source: DiscoverySource, fetcher: Any) -> list[RawCandidate]:
        response = await fetcher.fetch(source.base_url)
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Check for Schema.org Event in JSON-LD
        jsonld_scripts = soup.find_all("script", type="application/ld+json")
        has_schema_event = False
        for script in jsonld_scripts:
            try:
                raw_json = script.string or script.get_text() or "{}"
                data = json.loads(raw_json)
                items = _extract_items(data)
                if items:
                    has_schema_event = True
                    break
            except Exception:
                continue

        if has_schema_event:
            logger.info("Found Schema.org Event on %s; routing to JsonLdConnector", source.base_url)
            candidates = await JsonLdConnector().extract_candidates(source, fetcher)
            if candidates:
                return candidates

        # 2. Check for RSS/Atom alternate feed link
        rss_link = soup.find(
            "link",
            rel=lambda r: bool(r and "alternate" in (r.lower() if isinstance(r, str) else [x.lower() for x in r])),
            type=lambda t: bool(t and ("rss+xml" in t.lower() or "atom+xml" in t.lower())),
        )
        if rss_link and rss_link.get("href"):
            feed_url = urljoin(source.base_url, rss_link["href"])
            logger.info("Found RSS/Atom alternate feed %s on %s; routing to RSSConnector", feed_url, source.base_url)
            feed_source = DiscoverySource(
                name=f"Feed: {source.name or source.base_url}",
                base_url=feed_url,
                source_type="rss",
                region=source.region,
                crawl_interval=source.crawl_interval,
            )
            rss_candidates = await RSSConnector().extract_candidates(feed_source, fetcher)
            if rss_candidates:
                return rss_candidates

        # 3. Trafilatura clean content extraction fallback
        trafilatura_candidate = self._extract_with_trafilatura(source, html_content, soup)
        if trafilatura_candidate:
            logger.info("Extracted event content with trafilatura for %s", source.base_url)
            return [trafilatura_candidate]

        # 4. Standard semantic HTML fallback
        return await HTMLConnector().extract_candidates(source, fetcher)

    def _extract_with_trafilatura(
        self,
        source: DiscoverySource,
        html_content: str,
        soup: BeautifulSoup,
    ) -> RawCandidate | None:
        """Extracts clean body text without boilerplate using trafilatura."""
        try:
            import trafilatura
            extracted_text = trafilatura.extract(
                html_content,
                include_links=True,
                include_comments=False,
                output_format="txt",
                url=source.base_url,
            )
        except ImportError:
            logger.debug("Trafilatura is not installed in the local environment; skipping")
            extracted_text = None
        except Exception as exc:
            logger.warning("Trafilatura extraction failed for %s: %s", source.base_url, exc)
            extracted_text = None

        if not extracted_text or len(extracted_text.strip()) < 30:
            return None

        # Title
        title_el = soup.find("title") or soup.find("h1")
        title = title_el.get_text().strip() if title_el else ""
        if not title:
            lines = [l.strip() for l in extracted_text.splitlines() if l.strip()]
            title = lines[0] if lines else "Untitled Event"

        # Dates from text
        start_date_str = extract_date_from_text(title) or extract_date_from_text(extracted_text)

        # Registration link from buttons / anchor tags
        reg_url = None
        for a in soup.find_all("a", href=True):
            link_text = (a.get_text() or "").lower()
            href_val = a["href"].lower()
            if any(k in link_text or k in href_val for k in ("register", "registration", "apply", "ticket", "rsvp")):
                reg_url = urljoin(source.base_url, a["href"])
                break

        return RawCandidate(
            title=title,
            url=source.base_url,
            description=extracted_text,
            short_description=extracted_text[:200] if extracted_text else None,
            start_date_str=start_date_str,
            registration_url=reg_url or source.base_url,
            raw_payload={"extractor": "trafilatura", "text_len": len(extracted_text)},
        )
