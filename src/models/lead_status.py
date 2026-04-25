"""SQLAlchemy ORM model for Lead Status tracking."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class LeadStatus(Base):
    """Tracks the sales pipeline status of a lead."""

    __tablename__ = "lead_statuses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False
    )
    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    lead = relationship("Lead", back_populates="status_info")

    def __repr__(self) -> str:
        return f"<LeadStatus {self.status} for lead={self.lead_id}>"
