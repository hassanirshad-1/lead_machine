"""Pydantic schemas for Lead and Contact API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, Field


class ContactResponse(BaseModel):
    """Schema for contact info embedded in lead responses."""
    model_config = {"from_attributes": True}

    name: str | None
    email: str | None
    linkedin_url: str | None
    job_title: str | None = None
    headline: str | None = None
    location: str | None = None
    source: str
    confidence_score: float


class LeadStatusUpdate(BaseModel):
    """Schema for updating lead pipeline status."""
    status: str = Field(
        ...,
        pattern="^(new|to_contact|in_progress|contacted|closed_won|closed_lost|not_interested)$",
    )
    assigned_to: str | None = None
    notes: str | None = None


class LeadResponse(BaseModel):
    """Schema for lead API responses."""
    model_config = {"from_attributes": True}

    id: str
    campaign_id: str
    business_name: str
    address: str | None
    phone: str | None
    business_type: str | None
    website_url: str | None
    website_type: str
    has_app: bool | None
    rating: float | None
    review_count: int | None
    google_maps_url: str | None
    quality_score: int
    created_at: datetime

    # Nested
    contact: ContactResponse | None = None
    status: str | None = None
    assigned_to: str | None = None
    notes: str | None = None


class LeadListResponse(BaseModel):
    """Paginated list of leads."""
    leads: list[LeadResponse]
    total: int
    qualified: int
