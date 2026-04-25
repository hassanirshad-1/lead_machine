"""Pipeline orchestrator — runs the full Discovery → Qualification → Enrichment → Scoring → DB pipeline."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.campaign import Campaign
from src.models.contact import Contact
from src.models.lead import Lead
from src.models.lead_status import LeadStatus
from src.services.discovery import DiscoveryService
from src.services.enrichment import EnrichmentService
from src.services.qualification import classify_website, qualify_leads
from src.services.scoring import determine_auto_status, score_lead

logger = logging.getLogger(__name__)


async def run_campaign_pipeline(campaign_id: str, session: AsyncSession) -> dict:
    """Execute the full lead generation pipeline for a campaign.

    Steps:
        1. Discovery — search OpenStreetMap Overpass API
        2. Qualification — filter out businesses with real websites
        3. Enrichment — find owner/contact info (free methods)
        4. Scoring — assign quality score
        5. Persist — save everything to the database
    """
    # Load the campaign
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    # Mark as running
    campaign.status = "running"
    campaign.last_run_at = datetime.now(timezone.utc)
    campaign.error_message = None
    await session.flush()

    try:
        # --- Step 1: Discovery ---
        logger.info(f"[Pipeline] Step 1/4: Discovery for '{campaign.niche}' in '{campaign.city}' (grid scanning)")
        discovery = DiscoveryService()
        businesses = await discovery.search_wide(campaign.niche, campaign.city, campaign.country)

        if not businesses:
            campaign.status = "completed"
            campaign.total_found = 0
            campaign.total_qualified = 0
            await session.commit()
            return {"total_found": 0, "total_qualified": 0, "total_saved": 0}

        # --- Step 2: Qualification ---
        logger.info(f"[Pipeline] Step 2/4: Qualification ({len(businesses)} businesses)")
        qualified, disqualified = qualify_leads(businesses)

        # --- Step 3: Enrichment + Step 4: Scoring + Persist ---
        logger.info(f"[Pipeline] Step 3-4/4: Enrichment & Scoring ({len(qualified)} qualified leads)")
        enrichment = EnrichmentService()

        saved_count = 0
        for biz in qualified:
            # Check for duplicates (same place ID or same name)
            existing = await session.execute(
                select(Lead).where(
                    (Lead.google_place_id == biz.google_place_id) | 
                    (Lead.business_name == biz.business_name)
                )
            )
            if existing.scalar_one_or_none():
                logger.debug(f"  Skipping duplicate: {biz.business_name}")
                continue

            # Classify website
            website_type = classify_website(biz.website_url)

            # Enrichment
            enrichment_result = await enrichment.enrich(
                biz.business_name, campaign.city, biz.website_url
            )

            # Scoring
            quality_score = score_lead(biz, website_type, has_contact=enrichment_result.found)
            auto_status = determine_auto_status(quality_score)

            # Determine business type from types
            business_type = _extract_business_type(biz.types)

            # Create Lead
            lead = Lead(
                campaign_id=campaign.id,
                google_place_id=biz.google_place_id,
                business_name=biz.business_name,
                address=biz.address,
                latitude=biz.latitude,
                longitude=biz.longitude,
                phone=biz.phone,
                business_type=business_type,
                website_url=biz.website_url,
                website_type=website_type,
                rating=biz.rating,
                review_count=biz.review_count,
                google_maps_url=biz.google_maps_url,
                quality_score=quality_score,
            )
            session.add(lead)
            await session.flush()

            # Create Contact (if enrichment found something)
            contact = Contact(
                lead_id=lead.id,
                name=enrichment_result.owner_name,
                email=enrichment_result.email,
                phone=enrichment_result.phone,
                linkedin_url=enrichment_result.linkedin_url,
                job_title=enrichment_result.job_title,
                headline=enrichment_result.headline,
                location=enrichment_result.location,
                source=enrichment_result.source if enrichment_result.found else "pending",
                confidence_score=enrichment_result.confidence,
            )
            session.add(contact)

            # Create LeadStatus
            status = LeadStatus(
                lead_id=lead.id,
                status=auto_status,
            )
            session.add(status)

            saved_count += 1

        # Update campaign stats
        campaign.total_found = len(businesses)
        campaign.total_qualified = saved_count
        campaign.status = "completed"
        await session.commit()

        result = {
            "total_found": len(businesses),
            "total_qualified": len(qualified),
            "total_saved": saved_count,
            "total_disqualified": len(disqualified),
        }
        logger.info(f"[Pipeline] Complete: {result}")
        return result

    except Exception as e:
        logger.error(f"[Pipeline] Failed: {e}", exc_info=True)
        campaign.status = "failed"
        campaign.error_message = str(e)
        await session.commit()
        raise


def _extract_business_type(types: list[str]) -> str:
    """Extract a human-readable business type from types list."""
    type_map = {
        "cafe": "Cafe",
        "coffee_shop": "Cafe",
        "restaurant": "Restaurant",
        "gym": "Gym",
        "fitness_centre": "Gym",
        "hair_salon": "Salon",
        "hairdresser": "Salon",
        "beauty_salon": "Salon",
        "beauty": "Salon",
        "spa": "Spa",
        "barbershop": "Barbershop",
        "barber_shop": "Barbershop",
        "bakery": "Bakery",
        "bar": "Bar",
        "night_club": "Nightclub",
        "dentist": "Dental Clinic",
        "veterinary_care": "Vet Clinic",
        "pet": "Pet Store",
        "pet_store": "Pet Store",
        "florist": "Florist",
        "car_wash": "Car Wash",
        "laundry": "Laundry",
        "dry_cleaning": "Laundry",
        "real_estate_agency": "Real Estate",
    }

    for t in types:
        if t in type_map:
            return type_map[t]

    if types:
        return types[0].replace("_", " ").title()
    return "Business"
