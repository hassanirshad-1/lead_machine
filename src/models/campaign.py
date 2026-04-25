"""SQLAlchemy ORM model for Search Campaigns."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Campaign(Base):
    """A search campaign represents a single niche + city scraping job."""

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    niche: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="US")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    total_qualified: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Campaign {self.name} ({self.niche} in {self.city})>"
