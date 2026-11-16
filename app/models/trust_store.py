"""Trust Store ORM Model."""

from sqlalchemy import Column, String, Integer, CheckConstraint
from app.database import Base


class TrustStore(Base):
    """Stores the autonomy trust score per action type."""

    __tablename__ = "trust_store"

    action_type = Column(String(64), primary_key=True)
    success_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("success_count >= 0", name="check_success_count_non_negative"),
    )

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "success_count": self.success_count,
        }
