"""Action Log and Restoration Log ORM Models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, ForeignKey
from app.database import Base


class ActionLog(Base):
    """Append-only audit log capturing all executed mutations and their states."""

    __tablename__ = "action_log"

    action_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_type = Column(String(64), nullable=False, index=True)
    target_row_id = Column(Integer, ForeignKey("content_queue.id", ondelete="SET NULL"), nullable=True, index=True)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    is_restored = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_row_id": self.target_row_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "is_restored": self.is_restored,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RestorationLog(Base):
    """Append-only record of restoration events."""

    __tablename__ = "restoration_log"

    restoration_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String(36), ForeignKey("action_log.action_id", ondelete="CASCADE"), nullable=False, index=True)
    target_row_id = Column(Integer, nullable=True)
    restored_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "restoration_id": self.restoration_id,
            "action_id": self.action_id,
            "target_row_id": self.target_row_id,
            "restored_at": self.restored_at.isoformat() if self.restored_at else None,
            "details": self.details,
        }
