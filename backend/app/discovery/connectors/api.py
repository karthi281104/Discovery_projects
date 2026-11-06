import logging
from typing import Any
from urllib.parse import urljoin

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.models import DiscoverySource

logger = logging.getLogger(__name__)


class APIConnector(BaseConnector):
    """JSON REST API connector for documented event feeds and platform APIs."""

    async def extract_candidates(
        self,
        source: DiscoverySource,
        fetcher: Any,
    ) -> list[RawCandidate]:
        cfg = source.request_config or {}
        custom_headers = cfg.get("headers", {})

        response = await fetcher.fetch(source.base_url, headers=custom_headers)
        data = response.json()

        items_key = cfg.get("items_key")
        if items_key and isinstance(data, dict):
            items = data.get(items_key, [])
        elif isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Auto-detect common container keys
            for key in ("events", "items", "data", "results", "records"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            else:
                items = [data]
        else:
            items = []

        field_map = cfg.get("field_mapping", {})
        candidates: list[RawCandidate] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            def get_f(field_name: str, *fallback_names: str) -> Any:
                if field_name in field_map:
                    mapped = field_map[field_name]
                    if mapped in item:
                        return item[mapped]
                for name in (field_name, *fallback_names):
                    if name in item and item[name] is not None:
                        return item[name]
                return None

            title = get_f("title", "name", "event_name", "headline")
            if not title:
                continue

            url = get_f("url", "link", "event_url", "website")
            full_url = urljoin(source.base_url, str(url)) if url else source.base_url

            start_date_str = get_f("start_date", "starts_at", "startDate", "date", "start")
            end_date_str = get_f("end_date", "ends_at", "endDate", "end")
            description = get_f("description", "summary", "details", "desc")
            organizer = get_f("organizer", "organizer_name", "host", "by")
            banner_url = get_f("banner_url", "image", "image_url", "logo", "thumbnail")
            venue = get_f("venue", "location_name", "address")
            city = get_f("city", "town")
            district = get_f("district")
            mode = get_f("mode", "event_mode") or "offline"
            event_type = get_f("event_type", "type", "category")
            reg_url = get_f("registration_url", "ticket_url", "register_url") or full_url
            ext_id = get_f("id", "event_id", "slug")

            fee = None
            fee_raw = get_f("fee", "price", "participation_fee")
            if fee_raw is not None:
                try:
                    fee = float(fee_raw)
                except (ValueError, TypeError):
                    fee = None

            candidates.append(
                RawCandidate(
                    title=str(title).strip(),
                    url=full_url,
                    description=str(description).strip() if description else None,
                    short_description=str(description)[:200] if description else None,
                    start_date_str=str(start_date_str) if start_date_str else None,
                    end_date_str=str(end_date_str) if end_date_str else None,
                    organizer=str(organizer).strip() if organizer else None,
                    registration_url=str(reg_url) if reg_url else full_url,
                    banner_url=str(banner_url) if banner_url else None,
                    event_type=str(event_type).lower() if event_type else None,
                    mode=str(mode).lower() if mode else "offline",
                    venue=str(venue) if venue else None,
                    city=str(city) if city else None,
                    district=str(district) if district else None,
                    participation_fee=fee,
                    external_id=str(ext_id) if ext_id else full_url,
                    raw_payload=item,
                )
            )

        return candidates

