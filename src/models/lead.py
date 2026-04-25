"""SQLAlchemy ORM model for Leads (discovered businesses)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Lead(Base):
    """A business discovered via the API."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    google_place_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Business info
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Digital presence
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_type: Mapped[str] = mapped_column(
        String(20), default="none", nullable=False
    )  # "none", "social_only", "real"
    has_app: Mapped[bool | None] = mapped_column(nullable=True)

    # Quality signals
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scoring
    quality_score: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    campaign = relationship("Campaign", back_populates="leads")
    contact = relationship(
        "Contact", back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )
    status_info = relationship(
        "LeadStatus", back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lead {self.business_name} (score={self.quality_score})>"
