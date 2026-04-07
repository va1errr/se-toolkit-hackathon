"""
Integration tests for RAG edge cases — runs directly against the live DB.

Usage:
    cd backend
    python -m test_rag_integration
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import text

from app.config import settings
from app.services.rag import (
    extract_lab_numbers,
    retrieve_context,
    build_prompt,
    run_rag_pipeline,
)
from app.services.embeddings import embed_text


async def get_session():
    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session = AsyncSessionLocal()
    return session, engine


# =============================================================================
# TEST HELPERS
# =============================================================================

passed = 0
failed = 0


def check(condition, message):
    global passed, failed
    if condition:
        print(f"  ✅ {message}")
        passed += 1
    else:
        print(f"  ❌ {message}")
        failed += 1


# =============================================================================
# 1. extract_lab_numbers() — ALL PATTERNS
# =============================================================================

def test_extract_lab_numbers():
    print("\n" + "=" * 70)
    print(" TEST 1: extract_lab_numbers() — All mention patterns")
    print("=" * 70)

    cases = [
        # (input, expected_output, description)
        ("how do lists work in lab 3?", [3], "single lab lowercase"),
        ("Help with Lab 2", [2], "single lab title case"),
        ("Question about LAB 5", [5], "single lab uppercase"),
        ("stuck on lab #4", [4], "single lab with #"),
        ("lab1 question", [1], "single lab no space"),
        ("difference between lab 2 and lab 3", [2, 3], "two labs with 'and'"),
        ("compare lab 1, lab 4", [1, 4], "two labs comma-separated"),
        ("lab 1, lab 2, and lab 5", [1, 2, 5], "three labs"),
        ("explain concepts from lab 1, lab 2, lab 3, lab 4, and lab 5", [1, 2, 3, 4, 5], "FIVE labs"),
        ("lab #1, lab#2, lab #3, lab#4, lab #5", [1, 2, 3, 4, 5], "FIVE labs with #"),
        ("lab 3 and also lab 3 again", [3], "duplicate labs deduplicated"),
        ("lab 5, lab 2, lab 8, lab 1", [1, 2, 5, 8], "labs returned sorted"),
        ("what is a variable?", [], "no lab mentioned"),
        ("", [], "empty string"),
        ("general programming question about loops", [], "general question"),
        ("I'm working on lab 4 and can't figure it out", [4], "lab in middle of sentence"),
        ("Lab 3 is confusing me", [3], "lab at start"),
        ("explain this concept from lab 2", [2], "lab at end"),
        ("help with lab 4!", [4], "lab with punctuation"),
        ("Question: lab 4 exercise 3", [4], "lab with colon"),
        ("stuck on lab 3 (the file handling one)", [3], "lab with parentheses"),
        ('the "lab 5" assignment is hard', [5], "lab in quotes"),
        ("I work in a laboratory", [], "word 'laboratory' not matched"),
        ("which lab should I do?", [], "lab without number not matched"),
        ("lab 42 and lab 100", [42, 100], "large lab numbers"),
        ("lab 9", [9], "single-digit lab"),
        ("lab 12", [12], "double-digit lab"),
        ("lab 1, Lab #2, LAB 3, lab#4, lab 5", [1, 2, 3, 4, 5], "mixed formats"),
    ]

    for input_text, expected, description in cases:
        result = extract_lab_numbers(input_text)
        check(result == expected, f"{description}: {result} == {expected}")


# =============================================================================
# 2. retrieve_context() — DB integration
# =============================================================================

async def test_retrieve_context():
    print("\n" + "=" * 70)
    print(" TEST 2: retrieve_context() — DB integration")
    print("=" * 70)

    session, engine = await get_session()
    try:
        embedding = embed_text("How do lists work in Python?")

        # 2a. No lab filter — searches ALL labs
        docs = await retrieve_context(embedding, session, question_text="How do lists work?", lab_number_filter=None)
        check(isinstance(docs, list), "No filter: returns list")
        if docs:
            labs = sorted(set(d["lab_number"] for d in docs))
            check(len(labs) >= 1, f"No filter: references {len(labs)} lab(s): {labs}")
        else:
            check(False, "No filter: no docs returned (may be expected if DB empty)")

        # 2b. Single lab filter
        docs = await retrieve_context(embedding, session, question_text="How do lists work?", lab_number_filter=[2])
        check(isinstance(docs, list), "Single lab filter: returns list")
        all_lab_2 = all(d["lab_number"] == 2 for d in docs)
        check(all_lab_2, f"Single lab filter: ALL docs are from lab 2 (got {len(docs)} chunks)")

        # 2c. Five labs filter
        docs = await retrieve_context(embedding, session, question_text="Compare labs", lab_number_filter=[1, 2, 3, 4, 5])
        check(isinstance(docs, list), "Five lab filter: returns list")
        if docs:
            labs_in_result = set(d["lab_number"] for d in docs)
            all_valid = all(d["lab_number"] in [1, 2, 3, 4, 5] for d in docs)
            check(all_valid, f"Five lab filter: all docs from labs 1-5 (actual labs: {sorted(labs_in_result)})")
        else:
            check(False, "Five lab filter: no docs returned (labs may not exist yet)")

        # 2d. Non-existent lab
        docs = await retrieve_context(embedding, session, question_text="Lab 99?", lab_number_filter=[99])
        check(docs == [], f"Non-existent lab 99: returns empty list (got {len(docs)})")

        # 2e. Mixed existing + non-existing
        docs = await retrieve_context(embedding, session, question_text="Lab 1 and 99?", lab_number_filter=[1, 99])
        if docs:
            all_valid = all(d["lab_number"] in [1, 99] for d in docs)
            only_lab_1 = all(d["lab_number"] == 1 for d in docs)  # only lab 1 exists
            check(all_valid and only_lab_1, f"Mixed labs 1,99: only lab 1 chunks returned ({len(docs)} chunks)")
        else:
            check(False, "Mixed labs: no docs returned")

        # 2f. Verify ALL labs in DB are referenced when no filter
        result = await session.execute(text("SELECT DISTINCT lab_number FROM lab_doc ORDER BY lab_number"))
        all_labs_in_db = [row[0] for row in result.fetchall()]
        if docs := await retrieve_context(embedding, session, question_text="Python?", lab_number_filter=None):
            labs_referenced = sorted(set(d["lab_number"] for d in docs))
            # Not all labs may match a given question semantically, so just log
            print(f"  ℹ️  DB has labs: {all_labs_in_db}, query referenced labs: {labs_referenced}")

    finally:
        await session.close()
        await engine.dispose()


# =============================================================================
# 3. build_prompt() — verify all labs included in context
# =============================================================================

def test_build_prompt():
    print("\n" + "=" * 70)
    print(" TEST 3: build_prompt() — All labs included in prompt")
    print("=" * 70)

    def make_doc(lab_number, title="Test Lab", content="Test content", chunk_index=0, num_chunks=1):
        return {
            "id": f"doc-{lab_number}-{chunk_index}",
            "lab_number": lab_number,
            "title": title,
            "content": content,
            "similarity": 0.8,
            "chunk_index": chunk_index,
            "num_chunks": num_chunks,
        }

    # 3a. Single lab
    docs = [make_doc(3, "Data Structures", "Lists and dicts.")]
    messages = build_prompt("What are lists?", "Explain.", docs)
    content = messages[1]["content"]
    check("Lab 3" in content, "Single lab: Lab 3 appears in prompt")
    check("Lists and dicts." in content, "Single lab: content appears in prompt")

    # 3b. Five labs
    docs = [make_doc(i, f"Lab {i}", f"Content for lab {i}") for i in range(1, 6)]
    messages = build_prompt("Compare all labs", "Explain differences.", docs)
    content = messages[1]["content"]
    for i in range(1, 6):
        check(f"Lab {i}" in content and f"Content for lab {i}" in content, f"Five labs: Lab {i} appears with content")

    # 3c. No context
    messages = build_prompt("Random?", "Random body.", [])
    content = messages[1]["content"]
    check("(No relevant lab materials found" in content, "No context: fallback message appears")

    # 3d. Multi-chunk single lab
    docs = [
        make_doc(2, "Data", f"Part {i}", chunk_index=i-1, num_chunks=3) for i in range(1, 4)
    ]
    messages = build_prompt("Question?", "Body.", docs)
    content = messages[1]["content"]
    check("Lab 2 (part 1/3)" in content, "Multi-chunk: part 1/3 labeled")
    check("Lab 2 (part 2/3)" in content, "Multi-chunk: part 2/3 labeled")
    check("Lab 2 (part 3/3)" in content, "Multi-chunk: part 3/3 labeled")

    # 3e. Labs sorted in prompt
    docs = [make_doc(5, "E", "C5"), make_doc(2, "B", "C2"), make_doc(4, "D", "C4")]
    messages = build_prompt("Q?", "B.", docs)
    content = messages[1]["content"]
    pos = [content.find(f"Lab {i}") for i in [2, 4, 5]]
    check(pos[0] < pos[1] < pos[2], f"Labs sorted in prompt: positions {pos} are ascending")

    # 3f. System prompt mentions multiple labs
    docs = [make_doc(1, "A", "C1"), make_doc(2, "B", "C2")]
    messages = build_prompt("Q?", "B.", docs)
    sys_content = messages[0]["content"]
    check("multiple labs" in sys_content.lower(), "System prompt: mentions 'multiple labs'")
    check("synthesize" in sys_content.lower(), "System prompt: mentions 'synthesize'")


# =============================================================================
# 4. FULL PIPELINE — live LLM call
# =============================================================================

async def test_full_pipeline():
    print("\n" + "=" * 70)
    print(" TEST 4: Full RAG pipeline — live LLM calls")
    print("=" * 70)

    session, engine = await get_session()
    try:
        # 4a. Single lab
        print("\n  --- 4a. Single lab: 'lab 2' ---")
        answer, confidence, labs = await run_rag_pipeline(
            "Lab 2 question",
            "How do I use append() in lab 2?",
            session,
        )
        check(len(answer) > 0, f"Single lab: answer returned ({len(answer)} chars)")
        check(0.0 <= confidence <= 1.0, f"Single lab: confidence={confidence:.2f}")
        check(all(lab == 2 for lab in labs), f"Single lab: all referenced labs are [2], got {labs}")

        # 4b. Five labs
        print("\n  --- 4b. Five labs: 'lab 1, 2, 3, 4, 5' ---")
        answer, confidence, labs = await run_rag_pipeline(
            "Compare all labs",
            "What are the differences between lab 1, lab 2, lab 3, lab 4, and lab 5?",
            session,
        )
        check(len(answer) > 0, f"Five labs: answer returned ({len(answer)} chars)")
        check(0.0 <= confidence <= 1.0, f"Five labs: confidence={confidence:.2f}")
        labs_valid = all(lab in [1, 2, 3, 4, 5] for lab in labs)
        check(labs_valid, f"Five labs: all labs in [1-5], got {labs}")

        # 4c. No lab mentioned
        print("\n  --- 4c. No lab mentioned ---")
        answer, confidence, labs = await run_rag_pipeline(
            "General question",
            "What is a variable in Python?",
            session,
        )
        check(len(answer) > 0, f"No lab: answer returned ({len(answer)} chars)")
        check(0.0 <= confidence <= 1.0, f"No lab: confidence={confidence:.2f}")
        print(f"  ℹ️  No lab: referenced labs = {labs}")

        # 4d. Non-existent lab
        print("\n  --- 4d. Non-existent lab 99 ---")
        answer, confidence, labs = await run_rag_pipeline(
            "Lab 99 question",
            "How do I complete lab 99?",
            session,
        )
        check(len(answer) > 0, f"Non-existent lab: answer returned ({len(answer)} chars)")
        check(labs == [], f"Non-existent lab: no labs referenced, got {labs}")

        # 4e. Implicit/prioritized — mentions lab but question is generic
        print("\n  --- 4e. Implicit lab mention in title only ---")
        answer, confidence, labs = await run_rag_pipeline(
            "Lab 1 help",
            "I don't understand anything, please explain.",
            session,
        )
        check(len(answer) > 0, f"Implicit lab: answer returned ({len(answer)} chars)")
        lab_1_only = all(lab == 1 for lab in labs) if labs else True
        check(lab_1_only, f"Implicit lab: all labs are [1], got {labs}")

        # 4f. Two labs — synthesis
        print("\n  --- 4f. Two labs: 'lab 1 and lab 3' ---")
        answer, confidence, labs = await run_rag_pipeline(
            "Compare lab 1 and lab 3",
            "What is the difference between lab 1 and lab 3?",
            session,
        )
        check(len(answer) > 0, f"Two labs: answer returned ({len(answer)} chars)")
        labs_valid = all(lab in [1, 3] for lab in labs)
        check(labs_valid, f"Two labs: all labs in [1,3], got {labs}")

    finally:
        await session.close()
        await engine.dispose()


# =============================================================================
# MAIN
# =============================================================================

async def main():
    global passed, failed

    test_extract_lab_numbers()
    test_build_prompt()
    await test_retrieve_context()
    await test_full_pipeline()

    print("\n" + "=" * 70)
    print(f" TOTAL RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print(" 🎉 ALL TESTS PASSED!")
    else:
        print(f" ⚠️  {failed} test(s) failed — see above.")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
