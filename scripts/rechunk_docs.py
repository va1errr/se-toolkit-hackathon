#!/usr/bin/env python3
"""
One-time migration script to re-chunk existing lab docs in the database.

Run this AFTER applying the Alembic migration that adds chunk_index/num_chunks columns.
It will:
1. Find all lab_doc entries with content > 15,000 chars
2. Split each into chunks at natural markdown boundaries
3. Delete the original oversized rows and insert new chunk rows with embeddings

Usage:
    cd backend
    python ../scripts/rechunk_docs.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, create_engine, select

from app.config import settings
from app.models.models import LabDoc
from app.services.embeddings import EmbeddingService
from app.services.chunker import chunk_lab_content


def rechunk_existing_docs():
    """Find oversized docs and re-chunk them."""
    engine = create_engine(settings.sync_database_url)
    svc = EmbeddingService()

    with Session(engine) as session:
        # Get all docs ordered by lab_number so we process them predictably
        docs = session.exec(select(LabDoc).order_by(LabDoc.lab_number)).all()

        if not docs:
            print("No lab documents found.")
            return

        # Group by (lab_number, chunk_index) to find which are already chunked
        # A doc is "already chunked" if num_chunks > 1 and content < 15K
        oversized = [d for d in docs if len(d.content) > 15_000]
        already_chunked = [d for d in docs if len(d.content) <= 15_000]

        print(f"Found {len(docs)} lab doc entries:")
        print(f"  - {len(already_chunked)} already within chunk size")
        print(f"  - {len(oversized)} need re-chunking")

        if not oversized:
            print("\n✅ No re-chunking needed — all docs are under 15K chars.")
            return

        # Show what will be chunked
        for doc in oversized:
            print(f"  ✂️  Lab {doc.lab_number}: {doc.title[:60]}... ({len(doc.content):,} chars)")

        confirm = input(f"\nRe-chunk {len(oversized)} doc(s)? (y/N): ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

        total_chunks_created = 0
        total_docs_removed = 0

        for doc in oversized:
            print(f"\nProcessing Lab {doc.lab_number}: {doc.title}...")
            chunks = chunk_lab_content(doc.content, title=doc.title)
            print(f"  Split into {len(chunks)} chunks (sizes: {[len(c) for c in chunks]})")

            # Generate embeddings for all chunks
            embeddings = svc.embed_many(chunks)

            # Create new chunk rows
            for idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
                new_doc = LabDoc(
                    lab_number=doc.lab_number,
                    title=doc.title,
                    content=chunk_content,
                    embedding=embedding,
                    chunk_index=idx,
                    num_chunks=len(chunks),
                )
                session.add(new_doc)

            total_chunks_created += len(chunks)

            # Delete the original oversized doc
            session.delete(doc)
            total_docs_removed += 1

        session.commit()

        print(f"\n✅ Done!")
        print(f"  Removed {total_docs_removed} oversized doc(s)")
        print(f"  Created {total_chunks_created} chunk(s)")

        # Final summary
        all_docs = session.exec(select(LabDoc).order_by(LabDoc.lab_number, LabDoc.chunk_index)).all()
        grouped = {}
        for doc in all_docs:
            grouped.setdefault(doc.lab_number, []).append(doc)

        print(f"\nFinal state: {len(all_docs)} total chunk(s) across {len(grouped)} lab(s)")
        for lab_num in sorted(grouped.keys()):
            lab_docs = grouped[lab_num]
            title = lab_docs[0].title
            chunk_count = len(lab_docs)
            sizes = [len(d.content) for d in lab_docs]
            print(f"  Lab {lab_num}: {title[:50]} — {chunk_count} chunk(s), sizes: {sizes}")


if __name__ == "__main__":
    rechunk_existing_docs()
