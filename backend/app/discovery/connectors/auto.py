from typing import Any

from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.discovery.connectors.html import HTMLConnector
from app.discovery.connectors.jsonld import JsonLdConnector
from app.models import DiscoverySource


class AutoConnector(BaseConnector):
    """Try structured event data first, then configured semantic HTML extraction."""

    async def extract_candidates(self, source: DiscoverySource, fetcher: Any) -> list[RawCandidate]:
        candidates = await JsonLdConnector().extract_candidates(source, fetcher)
        if candidates:
            return candidates
        return await HTMLConnector().extract_candidates(source, fetcher)
