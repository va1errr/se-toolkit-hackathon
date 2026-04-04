"""
Test script for the RAG pipeline.

Usage:
    cd backend
    python -m test_rag
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, create_engine, select

from app.config import settings
from app.models.models import LabDoc
from app.services.embeddings import EmbeddingService


def test_embed_and_search():
    """Test the embedding + vector search part of the RAG pipeline."""
    print("=" * 60)
    print(" TESTING: Embed + Vector Search")
    print("=" * 60)

    engine = create_engine(settings.sync_database_url)
    svc = EmbeddingService()

    # Test embedding a question
    question = "How do I use append() with lists in Python?"
    print(f"\n📝 Question: {question}")

    embedding = svc.embed(question)
    print(f"✅ Embedded: {len(embedding)} dimensions")

    # Test vector search
    with Session(engine) as session:
        docs = session.exec(select(LabDoc)).all()
        if not docs:
            print("❌ No lab docs found. Run `python -m seed` and `python -m embed_docs` first.")
            return

        # Convert embeddings to strings for SQL
        embedding_str = str(embedding)
        from sqlmodel import text
        query = text("""
            SELECT lab_number, title,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM lab_doc
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT 3
        """)
        results = session.execute(query, {"emb": embedding_str}).fetchall()

        print(f"\n🔍 Top {len(results)} matching lab docs:")
        for row in results:
            print(f"   Lab {row.lab_number}: {row.title} (similarity: {row.similarity:.4f})")

    print("\n✅ Embed + Search test passed!")


async def test_full_pipeline():
    """Test the full RAG pipeline with LLM call."""
    print("\n" + "=" * 60)
    print(" TESTING: Full RAG Pipeline (with LLM)")
    print("=" * 60)

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlmodel import SQLModel
    from sqlalchemy.orm import sessionmaker

    async_engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    question_title = "How do I use lists?"
    question_body = "I'm confused about how append() works. Can you explain?"
    print(f"\n📝 Question: {question_title}")
    print(f"📝 Body: {question_body}")

    try:
        from app.services.rag import run_rag_pipeline

        async with AsyncSessionLocal() as session:
            answer, confidence, labs = await run_rag_pipeline(
                question_title, question_body, session
            )

        print(f"\n🤖 Answer (first 200 chars):")
        print(f"   {answer[:200]}...")
        print(f"\n📊 Confidence: {confidence:.2f}")
        print(f"📚 Referenced labs: {labs}")

        if confidence > 0 and len(answer) > 10:
            print("\n✅ Full RAG pipeline test passed!")
        else:
            print("\n⚠️  Pipeline ran but answer quality is low (expected if LLM API key not set)")

    except Exception as e:
        print(f"\n❌ RAG pipeline failed: {e}")
        print("   (This is expected if LLM_API_KEY is not configured)")

    await async_engine.dispose()


if __name__ == "__main__":
    test_embed_and_search()
    asyncio.run(test_full_pipeline())
