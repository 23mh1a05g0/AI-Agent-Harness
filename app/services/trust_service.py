"""Trust Store Management Service with concurrency safety."""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.trust_store import TrustStore


class TrustService:
    """Service to query and safely update action trust counters."""

    def get_or_create(self, db: Session, action_type: str) -> TrustStore:
        """Retrieve existing trust record or initialize with 0."""
        record = db.query(TrustStore).filter(TrustStore.action_type == action_type).first()
        if not record:
            record = TrustStore(action_type=action_type, success_count=0)
            db.add(record)
            db.commit()
            db.refresh(record)
        return record

    def get_trust(self, db: Session, action_type: str) -> int:
        """Get the current success_count for an action type."""
        record = self.get_or_create(db, action_type)
        return record.success_count

    def increment_trust(self, db: Session, action_type: str) -> int:
        """Atomically increment the success_count by exactly 1."""
        # Use row-level lock where supported
        query = db.query(TrustStore).filter(TrustStore.action_type == action_type)
        if db.bind and db.bind.dialect.name != "sqlite":
            query = query.with_for_update()

        record = query.first()
        if not record:
            record = TrustStore(action_type=action_type, success_count=1)
            db.add(record)
        else:
            record.success_count += 1

        db.commit()
        db.refresh(record)
        return record.success_count

    def decrement_trust(self, db: Session, action_type: str) -> int:
        """Safely decrement the success_count by 1 with a minimum floor of 0."""
        query = db.query(TrustStore).filter(TrustStore.action_type == action_type)
        if db.bind and db.bind.dialect.name != "sqlite":
            query = query.with_for_update()

        record = query.first()
        if not record:
            record = TrustStore(action_type=action_type, success_count=0)
            db.add(record)
        else:
            record.success_count = max(0, record.success_count - 1)

        db.commit()
        db.refresh(record)
        return record.success_count

    def list_trust(self, db: Session) -> List[TrustStore]:
        """List all registered trust counters."""
        return db.query(TrustStore).all()


trust_service = TrustService()
