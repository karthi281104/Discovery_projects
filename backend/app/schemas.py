from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=140)
    description: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class LocationBase(BaseModel):
    name: str
    city: str
    state: str = "Tamil Nadu"
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LocationCreate(LocationBase):
    pass


class LocationRead(LocationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EventBase(BaseModel):
    title: str
    slug: str | None = None
    short_description: str | None = None
    description: str | None = None
    start_date: datetime
    end_date: datetime | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    organizer: str | None = None
    organizer_name: str | None = None
    ticket_url: str | None = None
    registration_url: str | None = None
    image_url: str | None = None
    banner_url: str | None = None
    event_type: str = "other"
    mode: str = "offline"
    status: str = "draft"
    city: str | None = None
    district: str | None = None
    venue: str | None = None
    state: str = "Tamil Nadu"
    is_published: bool = False
    is_featured: bool = False
    category_id: int | None = None
    location_id: int | None = None
    category: CategoryRead | None = None
    location: LocationRead | None = None


class EventCreate(EventBase):
    pass


class EventRead(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
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
