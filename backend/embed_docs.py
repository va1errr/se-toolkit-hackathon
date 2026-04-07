"""
CLI script to embed all lab documents in the database.

Reads lab_doc entries, generates embeddings using sentence-transformers,
and updates the embedding column.

If any docs are larger than the chunking threshold, they are split into
smaller chunks (with new rows created) and the original oversized row is deleted.

Usage:
    cd backend
    python -m embed_docs
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, create_engine, select

from app.config import settings
from app.models.models import LabDoc
from app.services.embeddings import EmbeddingService
from app.services.chunker import chunk_lab_content


def embed_all_lab_docs():
    """Generate and store embeddings for all lab documents.

    Also chunks any oversized docs into smaller pieces for better RAG retrieval.
    """
    engine = create_engine(settings.sync_database_url)
    svc = EmbeddingService()

    with Session(engine) as session:
        docs = session.exec(select(LabDoc).order_by(LabDoc.lab_number)).all()
        if not docs:
            print("No lab documents found. Run `python -m seed` first.")
            return

        print(f"Found {len(docs)} lab document entries.")

        # Phase 1: Re-chunk any oversized docs
        chunks_to_add = []
        docs_to_delete = []

        for doc in docs:
            if len(doc.content) > 15_000:
                print(f"  ✂️  Chunking Lab {doc.lab_number}: {doc.title} ({len(doc.content):,} chars)")
                chunks = chunk_lab_content(doc.content, title=doc.title)

                for idx, chunk_content in enumerate(chunks):
                    embedding = svc.embed(chunk_content)
                    new_doc = LabDoc(
                        lab_number=doc.lab_number,
                        title=doc.title,
                        content=chunk_content,
                        embedding=embedding,
                        chunk_index=idx,
                        num_chunks=len(chunks),
                    )
                    chunks_to_add.append(new_doc)

                docs_to_delete.append(doc)

        if docs_to_delete:
            for doc in docs_to_delete:
                session.delete(doc)
            session.flush()
            print(f"  Removed {len(docs_to_delete)} oversized doc(s)")

        for new_doc in chunks_to_add:
            session.add(new_doc)
        session.commit()

        if chunks_to_add:
            print(f"  Added {len(chunks_to_add)} chunk(s)")

        # Phase 2: Embed any docs missing embeddings
        docs = session.exec(select(LabDoc).where(LabDoc.embedding == None)).all()  # noqa: E711
        if docs:
            texts = [d.content for d in docs]
            print(f"  Embedding {len(docs)} doc(s)...")
            embeddings = svc.embed_many(texts)

            for doc, embedding in zip(docs, embeddings):
                doc.embedding = embedding
                session.add(doc)

            session.commit()
            print(f"  Embedded {len(docs)} doc(s)")

        # Summary
        all_docs = session.exec(select(LabDoc).order_by(LabDoc.lab_number)).all()
        grouped = {}
        for doc in all_docs:
            grouped.setdefault(doc.lab_number, []).append(doc)

        print(f"\nSummary: {len(all_docs)} total chunk(s) across {len(grouped)} lab(s)")
        for lab_num in sorted(grouped.keys()):
            lab_docs = grouped[lab_num]
            title = lab_docs[0].title
            chunk_count = len(lab_docs)
            if chunk_count == 1:
                print(f"  Lab {lab_num}: {title} (1 chunk, {len(lab_docs[0].content):,} chars)")
            else:
                sizes = [len(d.content) for d in lab_docs]
                print(f"  Lab {lab_num}: {title} ({chunk_count} chunks, sizes: {sizes})")


if __name__ == "__main__":
    embed_all_lab_docs()
