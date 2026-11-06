import json
import logging
from typing import Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.models import DiscoverySource

logger = logging.getLogger(__name__)

EVENT_TYPES_SET = {
    "event", "businessevent", "educationevent", "exhibitionevent", "festival",
    "foodevent", "hackathon", "literaryevent", "musicevent", "socialevent",
    "sportsevent", "theaterevent", "visualartsevent", "screeningevent", "danceevent",
}


def _is_event_type(type_val: Any) -> bool:
    if isinstance(type_val, str):
        return type_val.lower().replace("schema.org/", "") in EVENT_TYPES_SET
    if isinstance(type_val, list):
        return any(_is_event_type(t) for t in type_val)
    return False


def _extract_items(data: Any) -> list[dict]:
    items: list[dict] = []
    if isinstance(data, list):
        for item in data:
            items.extend(_extract_items(item))
    elif isinstance(data, dict):
        if "@graph" in data:
            items.extend(_extract_items(data["@graph"]))
        elif _is_event_type(data.get("@type")):
            items.append(data)
    return items


class JsonLdConnector(BaseConnector):
    """Extracts Schema.org Event data embedded in HTML <script type="application/ld+json"> tags."""

    async def extract_candidates(
        self,
        source: DiscoverySource,
        fetcher: Any,
    ) -> list[RawCandidate]:
        response = await fetcher.fetch(source.base_url)
        soup = BeautifulSoup(response.text, "html.parser")

        scripts = soup.find_all("script", type=lambda t: t and "ld+json" in t.lower())
        candidates: list[RawCandidate] = []

        for script in scripts:
            text = script.string or script.get_text()
            if not text or not text.strip():
                continue
            try:
                data = json.loads(text.strip())
            except Exception as exc:
                logger.debug("Failed parsing JSON-LD script from %s: %exc", source.base_url, exc)
                continue

            event_items = _extract_items(data)
            for item in event_items:
                title = item.get("name") or item.get("headline")
                if not title:
                    continue

                event_url = item.get("url")
                if event_url:
                    event_url = urljoin(source.base_url, event_url)
                else:
                    event_url = source.base_url

                # Dates
                start_date_str = item.get("startDate")
                end_date_str = item.get("endDate")

                # Organizer
                organizer_data = item.get("organizer")
                organizer_name = None
                organizer_url = None
                if isinstance(organizer_data, dict):
                    organizer_name = organizer_data.get("name")
                    organizer_url = organizer_data.get("url")
                elif isinstance(organizer_data, str):
                    organizer_name = organizer_data

                # Location & Mode
                location_data = item.get("location")
                venue = None
                city = None
                district = None
                mode = "offline"

                mode_val = str(item.get("eventAttendanceMode", "")).lower()
                if "online" in mode_val:
                    mode = "online"
                elif "mixed" in mode_val or "hybrid" in mode_val:
                    mode = "hybrid"

                if isinstance(location_data, dict):
                    loc_type = str(location_data.get("@type", "")).lower()
                    if "virtual" in loc_type:
                        mode = "online"
                    else:
                        venue = location_data.get("name")
                        address = location_data.get("address")
                        if isinstance(address, dict):
                            city = address.get("addressLocality")
                            district = address.get("addressRegion")
                        elif isinstance(address, str):
                            city = address
                elif isinstance(location_data, str):
                    venue = location_data

                # Image
                image_data = item.get("image")
                banner_url = None
                if isinstance(image_data, str):
                    banner_url = image_data
                elif isinstance(image_data, list) and image_data and isinstance(image_data[0], str):
                    banner_url = image_data[0]
                elif isinstance(image_data, dict):
                    banner_url = image_data.get("url")

                # Price / Offers
                offers = item.get("offers")
                fee = None
                currency = "INR"
                ticket_url = None
                if isinstance(offers, dict):
                    try:
                        fee = float(offers.get("price", 0))
                    except (ValueError, TypeError):
                        fee = None
                    currency = offers.get("priceCurrency") or "INR"
                    ticket_url = offers.get("url")
                elif isinstance(offers, list) and offers and isinstance(offers[0], dict):
                    try:
                        fee = float(offers[0].get("price", 0))
                    except (ValueError, TypeError):
                        fee = None
                    currency = offers[0].get("priceCurrency") or "INR"
                    ticket_url = offers[0].get("url")

                description = item.get("description") or ""

                candidates.append(
                    RawCandidate(
                        title=str(title).strip(),
                        url=event_url,
                        description=str(description).strip() if description else None,
                        short_description=str(description)[:200] if description else None,
                        start_date_str=str(start_date_str) if start_date_str else None,
                        end_date_str=str(end_date_str) if end_date_str else None,
                        organizer=str(organizer_name).strip() if organizer_name else None,
                        organizer_website=str(organizer_url) if organizer_url else None,
                        registration_url=ticket_url or event_url,
                        banner_url=banner_url,
                        mode=mode,
                        venue=venue,
                        city=city,
                        district=district,
                        participation_fee=fee,
                        currency=currency,
                        external_id=str(item.get("@id") or item.get("identifier") or event_url),
                        raw_payload=item,
                    )
                )

        return candidates

