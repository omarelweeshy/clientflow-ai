from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import date

SERVICES = ["AI automation", "Workflow integration", "Dashboard development", "Document intelligence", "Custom internal tool", "Other"]
STATUSES = ["NEW", "PROCESSING", "NEEDS_REVIEW", "QUALIFIED", "NURTURE", "DISQUALIFIED", "CONTACTED", "BOOKED", "WON", "LOST"]


class Intake(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    company: str = Field(default="", max_length=160)
    website: str = Field(default="", max_length=500)
    source: str = Field(default="portfolio", max_length=50)
    service: str = Field(min_length=1, max_length=80)
    enquiry: str = Field(min_length=20, max_length=5000)
    budget: Literal["unspecified", "under-500", "500-2000", "2000-5000", "5000-plus"] = "unspecified"
    deadline: str = Field(default="", max_length=40)
    contact_method: Literal["email", "phone"] = "email"
    country: str = Field(default="", max_length=80)
    consent: Literal[True]
    honeypot: str = Field(default="", max_length=200)

    @field_validator("website")
    @classmethod
    def valid_website(cls, value):
        if value:
            from urllib.parse import urlsplit

            parsed = urlsplit(value)
            if parsed.scheme not in ["http", "https"] or not parsed.hostname or parsed.username or any(c.isspace() for c in value):
                raise ValueError("Provide a valid HTTP or HTTPS website without credentials")
        return value

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=1000)
    deliverables: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(max_length=12)
    missing_information: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(max_length=12)
    urgency: Literal["normal", "urgent", "unspecified"]
    suggestions: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=8)


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget_weight: int = Field(default=30, ge=0, le=50)
    service_weight: int = Field(default=25, ge=0, le=50)
    completeness_weight: int = Field(default=20, ge=0, le=50)
    timeline_weight: int = Field(default=10, ge=0, le=50)
    business_weight: int = Field(default=10, ge=0, le=50)
    geography_weight: int = Field(default=5, ge=0, le=50)
    spam_penalty: int = Field(default=80, ge=0, le=100)
    low_budget_cap: int = Field(default=39, ge=0, le=100)
    high_threshold: int = Field(default=70, ge=1, le=100)
    medium_threshold: int = Field(default=40, ge=0, le=99)
    supported_services: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default=SERVICES[:-1], min_length=1, max_length=20)
    allowed_countries: list[str] = Field(default=[], max_length=50)
    probable_duplicates: bool = True
    review_urgent: bool = True
    booking_url: str = Field(default="https://cal.com/", max_length=500)
    followup_days: list[int] = Field(default=[3, 7], min_length=2, max_length=2)
    safe_automation: bool = False
    notifications_enabled: bool = False

    @field_validator("booking_url")
    @classmethod
    def booking(cls, value):
        if value and not value.startswith("https://"):
            raise ValueError("Booking URL must use HTTPS")
        return value

    @field_validator("followup_days")
    @classmethod
    def timing(cls, value):
        if not 1 <= value[0] < value[1] <= 90:
            raise ValueError("Use increasing days between 1 and 90")
        return value
