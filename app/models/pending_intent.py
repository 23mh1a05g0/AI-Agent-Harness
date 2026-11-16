"""Pending Intents ORM Model."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from app.database import Base


class PendingIntent(Base):
    """Stores actions waiting for Human-in-the-Loop (HITL) approval."""

    __tablename__ = "pending_intents"

    intent_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_type = Column(String(64), nullable=False, index=True)
    target_row_id = Column(Integer, nullable=True, index=True)
    prompt = Column(Text, nullable=False)
    validated_payload = Column(JSON, nullable=False)
    status = Column(String(32), default="PENDING", nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "action_type": self.action_type,
            "target_row_id": self.target_row_id,
            "prompt": self.prompt,
            "validated_payload": self.validated_payload,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }
