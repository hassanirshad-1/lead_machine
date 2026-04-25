"""API routes for Campaign management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.models.campaign import Campaign
from src.schemas.campaign import CampaignCreate, CampaignListResponse, CampaignResponse
from src.services.pipeline import run_campaign_pipeline

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("/", response_model=CampaignListResponse)
async def list_campaigns(session: AsyncSession = Depends(get_session)):
    """List all campaigns, newest first."""
    result = await session.execute(
        select(Campaign).order_by(Campaign.created_at.desc())
    )
    campaigns = result.scalars().all()

    return CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
        total=len(campaigns),
    )


@router.post("/", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new campaign (does NOT run it yet)."""
    campaign = Campaign(
        name=data.name,
        niche=data.niche,
        city=data.city,
        country=data.country,
    )
    session.add(campaign)
    await session.flush()
    await session.refresh(campaign)
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/run")
async def run_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Trigger the lead generation pipeline for a campaign."""
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status == "running":
        raise HTTPException(status_code=409, detail="Campaign is already running")

    result = await run_campaign_pipeline(campaign_id, session)
    return {"message": "Pipeline completed", **result}


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a campaign and all its leads."""
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await session.delete(campaign)
