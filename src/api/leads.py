"""API routes for Lead management."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database import get_session
from src.models.contact import Contact
from src.models.lead import Lead
from src.models.lead_status import LeadStatus
from src.schemas.lead import LeadListResponse, LeadResponse, LeadStatusUpdate

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    campaign_id: str | None = None,
    status: str | None = None,
    min_score: int = 0,
    search: str | None = None,
    sort_by: str = "quality_score",
    sort_dir: str = "desc",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List leads with optional filters, sorting, and pagination."""
    query = select(Lead).options(
        joinedload(Lead.contact),
        joinedload(Lead.status_info),
    )

    # Filters
    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)
    if min_score > 0:
        query = query.where(Lead.quality_score >= min_score)
    if search:
        query = query.where(Lead.business_name.ilike(f"%{search}%"))
    if status:
        query = query.join(LeadStatus).where(LeadStatus.status == status)

    # Count query (before pagination)
    count_query = select(sa_func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Qualified count
    qualified_query = select(sa_func.count()).select_from(
        query.where(Lead.quality_score >= 50).subquery()
    )
    qualified = (await session.execute(qualified_query)).scalar() or 0

    # Sorting
    sort_col = getattr(Lead, sort_by, Lead.quality_score)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    leads = result.unique().scalars().all()

    lead_responses = []
    for lead in leads:
        resp = LeadResponse(
            id=lead.id,
            campaign_id=lead.campaign_id,
            business_name=lead.business_name,
            address=lead.address,
            phone=lead.phone,
            business_type=lead.business_type,
            website_url=lead.website_url,
            website_type=lead.website_type,
            has_app=lead.has_app,
            rating=lead.rating,
            review_count=lead.review_count,
            google_maps_url=lead.google_maps_url,
            quality_score=lead.quality_score,
            created_at=lead.created_at,
            contact=lead.contact if lead.contact else None,
            status=lead.status_info.status if lead.status_info else "new",
            assigned_to=lead.status_info.assigned_to if lead.status_info else None,
            notes=lead.status_info.notes if lead.status_info else None,
        )
        lead_responses.append(resp)

    return LeadListResponse(leads=lead_responses, total=total, qualified=qualified)


@router.patch("/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    data: LeadStatusUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update the pipeline status of a lead."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await session.execute(
        select(LeadStatus).where(LeadStatus.lead_id == lead_id)
    )
    status = result.scalar_one_or_none()

    if status:
        status.status = data.status
        if data.assigned_to is not None:
            status.assigned_to = data.assigned_to
        if data.notes is not None:
            status.notes = data.notes
    else:
        status = LeadStatus(
            lead_id=lead_id,
            status=data.status,
            assigned_to=data.assigned_to,
            notes=data.notes,
        )
        session.add(status)

    return {"message": "Status updated", "status": data.status}


@router.get("/export/csv")
async def export_leads_csv(
    campaign_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Export leads as a CSV file."""
    query = select(Lead).options(
        joinedload(Lead.contact),
        joinedload(Lead.status_info),
    ).order_by(Lead.quality_score.desc())

    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)

    result = await session.execute(query)
    leads = result.unique().scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Business Name", "Address", "Phone", "Type", "Website",
        "Website Type", "Rating", "Reviews", "Quality Score",
        "Status", "Owner Name", "Job Title", "Owner Email",
        "Owner Phone", "LinkedIn URL", "Headline", "Owner Location", "Google Maps URL",
    ])

    for lead in leads:
        contact = lead.contact
        writer.writerow([
            lead.business_name,
            lead.address,
            lead.phone or "",
            lead.business_type or "",
            lead.website_url or "",
            lead.website_type,
            lead.rating or "",
            lead.review_count or "",
            lead.quality_score,
            lead.status_info.status if lead.status_info else "new",
            contact.name if contact else "",
            contact.job_title if contact else "",
            contact.email if contact else "",
            contact.phone if contact else "",
            contact.linkedin_url if contact else "",
            contact.headline if contact else "",
            contact.location if contact else "",
            lead.google_maps_url or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )
