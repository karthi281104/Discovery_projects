import logging
from typing import Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.models import DiscoverySource

logger = logging.getLogger(__name__)


class HTMLConnector(BaseConnector):
    """Deterministic HTML extractor using configurable CSS selectors or semantic event markup."""

    async def extract_candidates(
        self,
        source: DiscoverySource,
        fetcher: Any,
    ) -> list[RawCandidate]:
        response = await fetcher.fetch(source.base_url)
        soup = BeautifulSoup(response.text, "html.parser")

        cfg = source.request_config or {}
        item_sel = cfg.get("item_selector")
        title_sel = cfg.get("title_selector")
        date_sel = cfg.get("date_selector")
        url_sel = cfg.get("url_selector")
        desc_sel = cfg.get("desc_selector")
        organizer_sel = cfg.get("organizer_selector")

        candidates: list[RawCandidate] = []

        if item_sel:
            elements = soup.select(item_sel)
        else:
            # Common semantic listing selectors
            elements = (
                soup.select(".event-card, .event-item, .event, article.event, [data-event]")
                or soup.select("article")
            )

        for el in elements:
            # Title
            title = ""
            if title_sel:
                t_el = el.select_one(title_sel)
                if t_el:
                    title = t_el.get_text(strip=True)
            else:
                heading = el.select_one("h1, h2, h3, h4, .title")
                if heading:
                    title = heading.get_text(strip=True)

            if not title:
                continue

            # URL
            link = ""
            if url_sel:
                u_el = el.select_one(url_sel)
                if u_el and u_el.get("href"):
                    link = str(u_el["href"])
            else:
                a_tag = el.find("a", href=True)
                if a_tag:
                    link = str(a_tag["href"])

            full_url = urljoin(source.base_url, link) if link else source.base_url

            # Date
            date_str = None
            if date_sel:
                d_el = el.select_one(date_sel)
                if d_el:
                    date_str = d_el.get_text(strip=True)
            else:
                time_tag = el.find("time")
                if time_tag:
                    date_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
                else:
                    d_el = el.select_one(".date, .time, .event-date")
                    if d_el:
                        date_str = d_el.get_text(strip=True)

            # Description
            desc = None
            if desc_sel:
                de_el = el.select_one(desc_sel)
                if de_el:
                    desc = de_el.get_text(strip=True)
            else:
                p_tag = el.find("p")
                if p_tag:
                    desc = p_tag.get_text(strip=True)

            # Organizer
            organizer = None
            if organizer_sel:
                o_el = el.select_one(organizer_sel)
                if o_el:
                    organizer = o_el.get_text(strip=True)
            else:
                o_el = el.select_one(".organizer, .author, .by")
                if o_el:
                    organizer = o_el.get_text(strip=True)

            candidates.append(
                RawCandidate(
                    title=title,
                    url=full_url,
                    description=desc,
                    short_description=desc[:200] if desc else None,
                    start_date_str=date_str,
                    organizer=organizer,
                    registration_url=full_url,
                    external_id=full_url,
                    raw_payload={"title": title, "url": full_url, "date": date_str, "desc": desc},
                )
            )

        return candidates

