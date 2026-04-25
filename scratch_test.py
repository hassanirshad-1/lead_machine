import asyncio
from src.database import async_session_factory
from src.services.pipeline import run_campaign_pipeline
from src.models.campaign import Campaign
from sqlalchemy import select

async def test():
    async with async_session_factory() as session:
        # Create a new test campaign
        c = Campaign(name='Test 2', niche='Cafes', city='Toronto', country='CA')
        session.add(c)
        await session.commit()
        await session.refresh(c)
        
        try:
            print("Running pipeline...")
            await run_campaign_pipeline(c.id, session)
            print("Success!")
        except Exception as e:
            print("FAILED:", str(e))
        finally:
            await session.refresh(c)
            print("Campaign Error Message from DB:", c.error_message)

if __name__ == "__main__":
    asyncio.run(test())
