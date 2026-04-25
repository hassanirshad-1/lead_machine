"""Models package — import all models so Alembic can discover them."""

from src.database import Base
from src.models.campaign import Campaign
from src.models.contact import Contact
from src.models.lead import Lead
from src.models.lead_status import LeadStatus

__all__ = ["Base", "Campaign", "Contact", "Lead", "LeadStatus"]
