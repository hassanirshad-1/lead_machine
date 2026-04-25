import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.database import async_session_factory
from src.models.lead import Lead
from src.models.contact import Contact
from src.services.enrichment import EnrichmentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def enrich_all_existing():
    """Find leads without owner names and attempt to enrich them."""
    enrichment = EnrichmentService()
    
    async with async_session_factory() as session:
        # Get leads that have a contact but no name, or no contact at all
        query = (
            select(Lead)
            .options(joinedload(Lead.contact), joinedload(Lead.campaign))
        )
        result = await session.execute(query)
        leads = result.unique().scalars().all()
        
        leads_to_enrich = [
            l for l in leads 
            if not l.contact or not l.contact.name
        ]
        
        logger.info(f"Found {len(leads_to_enrich)} leads needing enrichment out of {len(leads)} total.")
        
        for lead in leads_to_enrich:
            logger.info(f"Enriching: {lead.business_name} in {lead.campaign.city}")
            
            try:
                result = await enrichment.enrich(
                    lead.business_name, 
                    lead.campaign.city, 
                    lead.website_url
                )
                
                if result.found:
                    if not lead.contact:
                        contact = Contact(
                            lead_id=lead.id,
                            name=result.owner_name,
                            email=result.email,
                            phone=result.phone,
                            linkedin_url=result.linkedin_url,
                            source=result.source,
                            confidence_score=result.confidence
                        )
                        session.add(contact)
                    else:
                        lead.contact.name = result.owner_name
                        lead.contact.email = result.email
                        lead.contact.phone = result.phone
                        lead.contact.linkedin_url = result.linkedin_url
                        lead.contact.source = result.source
                        lead.contact.confidence_score = result.confidence
                    
                    logger.info(f"  ✅ Found owner: {result.owner_name}")
                else:
                    logger.info("  ❌ No owner found.")
                
                # Commit every few leads to save progress
                await session.commit()
                # Rate limiting (brief pause between searches to avoid API bans)
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"  Error enriching {lead.business_name}: {e}")
                await session.rollback()

if __name__ == "__main__":
    asyncio.run(enrich_all_existing())
