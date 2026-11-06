from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models import DiscoverySource


@dataclass
class RawCandidate:
    title: str
    url: str
    description: str | None = None
    short_description: str | None = None
    start_date_str: str | None = None
    end_date_str: str | None = None
    registration_deadline_str: str | None = None
    organizer: str | None = None
    organizer_website: str | None = None
    registration_url: str | None = None
    official_website: str | None = None
    banner_url: str | None = None
    contact_email: str | None = None
    event_type: str | None = None
    mode: str | None = None
    venue: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = "Tamil Nadu"
    eligibility: str | None = None
    participation_fee: float | None = None
    currency: str = "INR"
    tags: list[str] = field(default_factory=list)
    external_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    @abstractmethod
    async def extract_candidates(
        self,
        source: DiscoverySource,
        fetcher: Any,
    ) -> list[RawCandidate]:
        """Fetches from source and returns raw un-normalized event candidates."""
        pass

