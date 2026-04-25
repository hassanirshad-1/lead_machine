"""Pydantic schemas for Campaign API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    """Schema for creating a new campaign."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Toronto Cafes Q2"])
    niche: str = Field(..., min_length=1, max_length=100, examples=["Cafes"])
    city: str = Field(..., min_length=1, max_length=100, examples=["Toronto"])
    country: str = Field(default="US", max_length=100, examples=["CA"])


class CampaignResponse(BaseModel):
    """Schema for campaign API responses."""
    model_config = {"from_attributes": True}

    id: str
    name: str
    niche: str
    city: str
    country: str
    status: str
    total_found: int
    total_qualified: int
    created_at: datetime
    last_run_at: datetime | None


class CampaignListResponse(BaseModel):
    """Paginated list of campaigns."""
    campaigns: list[CampaignResponse]
    total: int
