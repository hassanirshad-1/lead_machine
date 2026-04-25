"""SQLAlchemy ORM model for Contacts (decision-makers linked to leads)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Contact(Base):
    """Owner / decision-maker associated with a Lead."""

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50), default="google_search", nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    lead = relationship("Lead", back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact {self.name} for lead={self.lead_id}>"
