"""Dashboard page routes — server-rendered HTML with Jinja2 + HTMX."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database import get_session
from src.models.campaign import Campaign
from src.models.lead import Lead
from src.models.lead_status import LeadStatus

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/dashboard/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, session: AsyncSession = Depends(get_session)):
    """Main dashboard — KPI cards and recent campaigns."""
    total_leads = (await session.execute(
        select(sa_func.count(Lead.id))
    )).scalar() or 0

    qualified_leads = (await session.execute(
        select(sa_func.count(Lead.id)).where(Lead.quality_score >= 50)
    )).scalar() or 0

    to_contact = (await session.execute(
        select(sa_func.count(LeadStatus.id)).where(LeadStatus.status == "to_contact")
    )).scalar() or 0

    closed_won = (await session.execute(
        select(sa_func.count(LeadStatus.id)).where(LeadStatus.status == "closed_won")
    )).scalar() or 0

    result = await session.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).limit(10)
    )
    campaigns = result.scalars().all()

    total_campaigns = (await session.execute(
        select(sa_func.count(Campaign.id))
    )).scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total_leads": total_leads,
            "qualified_leads": qualified_leads,
            "to_contact": to_contact,
            "closed_won": closed_won,
            "campaigns": campaigns,
            "total_campaigns": total_campaigns,
        }
    )


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request, session: AsyncSession = Depends(get_session)):
    """Campaign manager page."""
    result = await session.execute(
        select(Campaign).order_by(Campaign.created_at.desc())
    )
    campaigns = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="campaigns.html",
        context={"campaigns": campaigns}
    )


@router.post("/campaigns/create", response_class=HTMLResponse)
async def create_campaign_form(
    request: Request,
    name: str = Form(...),
    niche: str = Form(...),
    city: str = Form(...),
    country: str = Form(default="US"),
    session: AsyncSession = Depends(get_session),
):
    """Handle campaign creation form submission."""
    campaign = Campaign(name=name, niche=niche, city=city, country=country)
    session.add(campaign)
    await session.flush()
    await session.refresh(campaign)
    return RedirectResponse(url="/campaigns", status_code=303)


@router.post("/campaigns/{campaign_id}/run", response_class=HTMLResponse)
async def run_campaign_dashboard(
    campaign_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Run a campaign from the dashboard."""
    from src.services.pipeline import run_campaign_pipeline

    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        await run_campaign_pipeline(campaign_id, session)
    except Exception:
        pass  # Error is saved on the campaign object

    return RedirectResponse(url="/campaigns", status_code=303)


@router.post("/campaigns/{campaign_id}/delete", response_class=HTMLResponse)
async def delete_campaign_dashboard(
    campaign_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Delete a campaign and all its leads from the dashboard."""
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await session.delete(campaign)
    return RedirectResponse(url="/campaigns", status_code=303)


@router.get("/leads", response_class=HTMLResponse)
async def leads_page(
    request: Request,
    campaign_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    min_score: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """Leads table page with filters."""
    query = select(Lead).options(
        joinedload(Lead.contact),
        joinedload(Lead.status_info),
        joinedload(Lead.campaign),
    )

    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)
    if status:
        query = query.join(LeadStatus).where(LeadStatus.status == status)
    if search:
        query = query.where(Lead.business_name.ilike(f"%{search}%"))
    if min_score > 0:
        query = query.where(Lead.quality_score >= min_score)

    query = query.order_by(Lead.quality_score.desc()).limit(1000)
    result = await session.execute(query)
    leads = result.unique().scalars().all()

    campaigns_result = await session.execute(
        select(Campaign).order_by(Campaign.name)
    )
    campaigns = campaigns_result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="leads.html",
        context={
            "leads": leads,
            "campaigns": campaigns,
            "current_campaign_id": campaign_id,
            "current_status": status,
            "current_search": search or "",
            "current_min_score": min_score,
        }
    )


@router.get("/leads/{lead_id}", response_class=HTMLResponse)
async def lead_detail_page(
    lead_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Detailed view of a single lead."""
    result = await session.execute(
        select(Lead).options(
            joinedload(Lead.contact),
            joinedload(Lead.status_info),
            joinedload(Lead.campaign),
        ).where(Lead.id == lead_id)
    )
    lead = result.unique().scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return templates.TemplateResponse(
        request=request,
        name="lead_detail.html",
        context={"lead": lead}
    )


@router.patch("/leads/{lead_id}/status", response_class=HTMLResponse)
async def update_status_htmx(
    lead_id: str,
    request: Request,
    status: str = Form(...),
    notes: str = Form(default=""),
    session: AsyncSession = Depends(get_session),
):
    """HTMX endpoint — update lead status inline and return the updated badge."""
    result = await session.execute(
        select(LeadStatus).where(LeadStatus.lead_id == lead_id)
    )
    lead_status = result.scalar_one_or_none()

    if lead_status:
        lead_status.status = status
        if notes:
            lead_status.notes = notes
    else:
        lead_status = LeadStatus(lead_id=lead_id, status=status, notes=notes)
        session.add(lead_status)

    status_colors = {
        "new": "#6b7280",
        "to_contact": "#f59e0b",
        "in_progress": "#3b82f6",
        "contacted": "#8b5cf6",
        "closed_won": "#10b981",
        "closed_lost": "#ef4444",
        "not_interested": "#6b7280",
    }
    color = status_colors.get(status, "#6b7280")
    label = status.replace("_", " ").title()

    return HTMLResponse(
        f'<span class="status-badge" style="background:{color}">{label}</span>'
    )
