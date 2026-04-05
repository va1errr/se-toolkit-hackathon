"""
Seed script to populate database with demo users and lab documents.

Usage:
    cd backend
    python -m seed

Or via Docker:
    docker compose exec backend python -m seed
"""

import asyncio
import os
import sys

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel, Session, create_engine, select

from app.config import settings
from app.models.models import User, LabDoc
from app.services.auth import hash_password


def seed_db():
    """Seed the database with demo data using synchronous connection."""
    # Use sync engine for seeding
    engine = create_engine(settings.sync_database_url)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Check if already seeded
        existing = session.exec(select(User)).first()
        if existing:
            print("Database already seeded. Skipping.")
            return

        print("Seeding database...")

        # --- Create users ---
        users = [
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            ),
        ]
        session.add_all(users)
        session.flush()
        print(f"  Created {len(users)} user: admin")

        # --- Create lab documents from markdown files ---
        seed_dir = os.path.dirname(os.path.abspath(__file__))
        md_files = sorted([
            f for f in os.listdir(seed_dir)
            if f.endswith(".md")
        ])

        lab_docs = []
        for md_file in md_files:
            filepath = os.path.join(seed_dir, md_file)
            content = open(filepath).read()

            # Extract title from first line or filename
            title = content.split("\n")[0].lstrip("# ").strip()
            if not title:
                title = md_file.replace(".md", "").replace("_", " ").title()

            # Extract lab number from filename
            lab_num = md_file.split("_")[1] if "_" in md_file else "0"
            try:
                lab_number = int(lab_num)
            except ValueError:
                lab_number = len(lab_docs) + 1

            doc = LabDoc(
                lab_number=lab_number,
                title=title,
                content=content,
            )
            lab_docs.append(doc)

        session.add_all(lab_docs)
        session.commit()

        print(f"  Created {len(lab_docs)} lab documents:")
        for doc in lab_docs:
            print(f"    - Lab {doc.lab_number}: {doc.title}")

        print("Seeding complete!")


if __name__ == "__main__":
    seed_db()
