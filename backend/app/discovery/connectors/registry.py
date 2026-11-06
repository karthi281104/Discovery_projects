from app.discovery.connectors.api import APIConnector
from app.discovery.connectors.base import BaseConnector, RawCandidate
from app.discovery.connectors.html import HTMLConnector
from app.discovery.connectors.jsonld import JsonLdConnector
from app.discovery.connectors.rss import RSSConnector

_REGISTRY: dict[str, BaseConnector] = {
    "rss": RSSConnector(),
    "jsonld": JsonLdConnector(),
    "html": HTMLConnector(),
    "api": APIConnector(),
}


def get_connector(source_type: str) -> BaseConnector:
    connector = _REGISTRY.get(source_type.lower())
    if not connector:
        raise ValueError(
            f"Unsupported source type '{source_type}'. "
            f"Supported types are: {', '.join(_REGISTRY.keys())}"
        )
    return connector

