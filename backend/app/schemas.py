import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

EventType = Literal[
    "hackathon",
    "conference",
    "workshop",
    "webinar",
    "competition",
    "symposium",
    "open_source",
    "startup",
    "research",
    "other",
]

EventMode = Literal["online", "offline", "hybrid"]

EventStatus = Literal["draft", "pending", "published", "rejected", "cancelled", "expired"]


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = None
    is_active: bool = True
    icon: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = None
    is_active: bool | None = None
    icon: str | None = None


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str


class LocationBase(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    city: str = Field(min_length=1, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    state: str = "Tamil Nadu"
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True
    is_verified_venue: bool = False


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    district: str | None = None
    state: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool | None = None
    is_verified_venue: bool | None = None


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    slug: str | None = Field(default=None, max_length=280)
    short_description: str | None = None
    description: str = Field(min_length=1)
    organizer_name: str = Field(min_length=1, max_length=180)
    organizer_website: str | None = None
    category_id: int | None = None
    location_id: int | None = None
    event_type: EventType = "other"
    mode: EventMode = "offline"
    start_date: datetime
    end_date: datetime | None = None
    registration_deadline: datetime | None = None
    registration_url: str = Field(min_length=1, max_length=500)
    official_website: str | None = None
    state: str = "Tamil Nadu"
    district: str | None = None
    city: str | None = None
    venue: str | None = None
    eligibility: str | None = None
    participation_fee: float | None = None
    currency: str = "INR"
    banner_url: str | None = None
    contact_email: EmailStr | str | None = None
    tags: list[str] = Field(default_factory=list)
    status: EventStatus = "draft"
    is_published: bool = False
    is_featured: bool = False

    # Optional legacy alias fields
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    organizer: str | None = None
    ticket_url: str | None = None
    image_url: str | None = None

    @field_validator("registration_url")
    @classmethod
    def validate_registration_url(cls, v: str) -> str:
        url = v.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("registration_url must begin with http:// or https://")
        return url

    @field_validator("organizer_website", "official_website", "banner_url")
    @classmethod
    def validate_optional_urls(cls, v: str | None) -> str | None:
        if v is None:
            return None
        url = v.strip()
        if not url:
            return None
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("URL must begin with http:// or https://")
        return url

    @field_validator("participation_fee")
    @classmethod
    def validate_fee(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("participation_fee cannot be negative")
        return v

    @model_validator(mode="before")
    @classmethod
    def sync_legacy_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if not data.get("start_date") and data.get("starts_at"):
                data["start_date"] = data["starts_at"]
            if not data.get("end_date") and data.get("ends_at"):
                data["end_date"] = data["ends_at"]
            if not data.get("organizer_name") and data.get("organizer"):
                data["organizer_name"] = data["organizer"]
            if not data.get("registration_url") and data.get("ticket_url"):
                data["registration_url"] = data["ticket_url"]
            if not data.get("banner_url") and data.get("image_url"):
                data["banner_url"] = data["image_url"]
            if data.get("is_published") and not data.get("status"):
                data["status"] = "published"
        return data

    @model_validator(mode="after")
    def validate_event_data(self) -> "EventBase":
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        if self.registration_deadline and self.start_date and self.registration_deadline > self.start_date:
            raise ValueError("registration_deadline must not be after start_date")
        if self.status == "published" or self.is_published:
            if not self.title or not self.description or not self.organizer_name or not self.registration_url or not self.start_date:
                raise ValueError("Published events require title, description, organizer_name, start_date, and registration_url")
        return self


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    slug: str | None = Field(default=None, max_length=280)
    short_description: str | None = None
    description: str | None = Field(default=None, min_length=1)
    organizer_name: str | None = Field(default=None, min_length=1, max_length=180)
    organizer_website: str | None = None
    category_id: int | None = None
    location_id: int | None = None
    event_type: EventType | None = None
    mode: EventMode | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    registration_deadline: datetime | None = None
    registration_url: str | None = Field(default=None, min_length=1, max_length=500)
    official_website: str | None = None
    state: str | None = None
    district: str | None = None
    city: str | None = None
    venue: str | None = None
    eligibility: str | None = None
    participation_fee: float | None = None
    currency: str | None = None
    banner_url: str | None = None
    contact_email: EmailStr | str | None = None
    tags: list[str] | None = None
    status: EventStatus | None = None
    is_published: bool | None = None
    is_featured: bool | None = None

    @field_validator("registration_url")
    @classmethod
    def validate_registration_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        url = v.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("registration_url must begin with http:// or https://")
        return url

    @field_validator("participation_fee")
    @classmethod
    def validate_fee(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("participation_fee cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_update_data(self) -> "EventUpdate":
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        if self.registration_deadline and self.start_date and self.registration_deadline > self.start_date:
            raise ValueError("registration_deadline must not be after start_date")
        return self


class EventRead(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: CategoryRead | None = None
    location: LocationRead | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EventList(BaseModel):
    items: list[EventRead]
    total: int
    page: int
    page_size: int
    pages: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminMetrics(BaseModel):
    total_events: int
    published_events: int
    draft_events: int
    pending_events: int
    rejected_events: int
    cancelled_events: int
    expired_events: int
    featured_events: int
    total_categories: int
    total_locations: int
