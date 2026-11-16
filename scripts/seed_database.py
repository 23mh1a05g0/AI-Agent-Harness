"""Database seeding script populating sample queue items and default trust store."""

import sys
import os
from datetime import datetime, timedelta

# Ensure repo root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, Base, engine
from app.models.content_queue import ContentQueue
from app.models.trust_store import TrustStore
from app.models.action_log import ActionLog, RestorationLog
from app.models.pending_intent import PendingIntent


def seed_database():
    """Seed initial records into content_queue and trust_store."""
    print("[*] Creating all database tables if not existing...")
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        print("[*] Cleaning existing test records...")
        db.query(RestorationLog).delete()
        db.query(ActionLog).delete()
        db.query(PendingIntent).delete()
        db.query(ContentQueue).delete()
        db.query(TrustStore).delete()
        db.commit()

        print("[*] Seeding default trust store (threshold baseline)...")
        db.add(TrustStore(action_type="purge", success_count=0))
        db.add(TrustStore(action_type="mark_posted", success_count=0))

        print("[*] Seeding content queue rows...")
        rows = [
            ContentQueue(id=1, content_text="First standard queued announcement.", status="PENDING"),
            ContentQueue(id=2, content_text="Second informative product teaser.", status="PENDING"),
            ContentQueue(id=3, content_text="Third customer highlight post.", status="PENDING"),
            ContentQueue(id=4, content_text="Fourth message: previously published news.", status="POSTED"),
            ContentQueue(
                id=5,
                content_text="Fifth message: strictly scheduled for next week launch embargo.",
                status="PENDING",
                scheduled_for=datetime.utcnow() + timedelta(days=7),
            ),
            ContentQueue(id=10, content_text="Tenth message: candidate row for safety test.", status="PENDING"),
        ]

        db.add_all(rows)
        db.commit()
        print(f"[+] Successfully seeded {len(rows)} content queue items and trust store baselines.")


if __name__ == "__main__":
    seed_database()
