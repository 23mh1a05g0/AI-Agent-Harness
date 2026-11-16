"""Content Queue ORM Model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class ContentQueue(Base):
    """Represents a queued social post or message item."""

    __tablename__ = "content_queue"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    content_text = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        """Serialize model state to dictionary for snapshotting."""
        return {
            "id": self.id,
            "content_text": self.content_text,
            "status": self.status,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
