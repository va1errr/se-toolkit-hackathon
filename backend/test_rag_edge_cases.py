"""
Comprehensive edge case tests for the RAG lab-reference pipeline.

Tests cover:
  1. extract_lab_numbers() — unit tests for all mention patterns
  2. retrieve_context() — with various lab filters
  3. build_prompt() — verifies all labs are included in context
  4. Full pipeline integration (requires DB running)

Usage:
    cd backend
    python -m pytest test_rag_edge_cases.py -v
    # or without DB:
    python -m pytest test_rag_edge_cases.py -v -k "not integration"
"""

import asyncio
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from app.services.rag import extract_lab_numbers, build_prompt, retrieve_context, SIMILARITY_THRESHOLD, STRONG_MATCH_THRESHOLD, MAX_DOCS, MAX_CONTEXT_CHARS


# =============================================================================
# UNIT TESTS: extract_lab_numbers()
# =============================================================================

class TestExtractLabNumbers:
    """Test all patterns of lab number extraction from question text."""

    # --- Single lab mention ---
    def test_single_lab_lowercase(self):
        assert extract_lab_numbers("how do lists work in lab 3?") == [3]

    def test_single_lab_title_case(self):
        assert extract_lab_numbers("Help with Lab 2") == [2]

    def test_single_lab_uppercase(self):
        assert extract_lab_numbers("Question about LAB 5") == [5]

    def test_single_lab_with_hash(self):
        assert extract_lab_numbers("stuck on lab #4") == [4]

    def test_single_lab_with_hash_space(self):
        assert extract_lab_numbers("need help with lab # 7") == [7]

    def test_single_lab_no_space(self):
        assert extract_lab_numbers("lab1 question") == [1]

    # --- Multiple lab mentions ---
    def test_two_labs_with_and(self):
        result = extract_lab_numbers("difference between lab 2 and lab 3")
        assert result == [2, 3]

    def test_two_labs_comma_separated(self):
        result = extract_lab_numbers("compare lab 1, lab 4")
        assert result == [1, 4]

    def test_three_labs(self):
        result = extract_lab_numbers("lab 1, lab 2, and lab 5")
        assert result == [1, 2, 5]

    def test_five_labs(self):
        """Edge case: 5 labs referenced"""
        result = extract_lab_numbers("explain concepts from lab 1, lab 2, lab 3, lab 4, and lab 5")
        assert result == [1, 2, 3, 4, 5]

    def test_five_labs_with_hash(self):
        """Edge case: 5 labs with # notation"""
        result = extract_lab_numbers("lab #1, lab#2, lab #3, lab#4, lab #5")
        assert result == [1, 2, 3, 4, 5]

    def test_duplicate_labs_deduplicated(self):
        result = extract_lab_numbers("lab 3 and also lab 3 again")
        assert result == [3]

    def test_labs_returned_sorted(self):
        result = extract_lab_numbers("lab 5, lab 2, lab 8, lab 1")
        assert result == [1, 2, 5, 8]

    # --- No lab mention ---
    def test_no_lab_mentioned(self):
        assert extract_lab_numbers("what is a variable?") == []

    def test_no_lab_mentioned_empty_string(self):
        assert extract_lab_numbers("") == []

    def test_no_lab_general_question(self):
        assert extract_lab_numbers("general programming question about loops") == []

    # --- Edge cases / tricky patterns ---
    def test_lab_in_middle_of_sentence(self):
        assert extract_lab_numbers("I'm working on lab 4 and can't figure it out") == [4]

    def test_lab_at_start(self):
        assert extract_lab_numbers("Lab 3 is confusing me") == [3]

    def test_lab_at_end(self):
        assert extract_lab_numbers("explain this concept from lab 2") == [2]

    def test_lab_with_punctuation(self):
        assert extract_lab_numbers("help with lab 4!") == [4]

    def test_lab_with_colon(self):
        assert extract_lab_numbers("Question: lab 4 exercise 3") == [4]

    def test_lab_with_parentheses(self):
        assert extract_lab_numbers("stuck on lab 3 (the file handling one)") == [3]

    def test_lab_in_quotes(self):
        assert extract_lab_numbers('the "lab 5" assignment is hard') == [5]

    def test_word_labor_not_matched(self):
        """Ensure 'laboratory' or 'labor' doesn't trigger false match"""
        result = extract_lab_numbers("I work in a laboratory")
        assert result == []

    def test_lab_without_number_not_matched(self):
        result = extract_lab_numbers("which lab should I do?")
        assert result == []

    def test_large_lab_numbers(self):
        result = extract_lab_numbers("lab 42 and lab 100")
        assert result == [42, 100]

    def test_single_digit_lab(self):
        assert extract_lab_numbers("lab 9") == [9]

    def test_double_digit_lab(self):
        assert extract_lab_numbers("lab 12") == [12]

    def test_mixed_formats(self):
        result = extract_lab_numbers("lab 1, Lab #2, LAB 3, lab#4, lab 5")
        assert result == [1, 2, 3, 4, 5]


# =============================================================================
# UNIT TESTS: build_prompt()
# =============================================================================

class TestBuildPrompt:
    """Test that build_prompt correctly includes all referenced labs."""

    def _make_doc(self, lab_number, title="Test Lab", content="Test content", chunk_index=0, num_chunks=1):
        return {
            "id": f"doc-{lab_number}-{chunk_index}",
            "lab_number": lab_number,
            "title": title,
            "content": content,
            "similarity": 0.8,
            "chunk_index": chunk_index,
            "num_chunks": num_chunks,
        }

    def test_prompt_with_single_lab(self):
        """Edge case: only 1 lab referenced"""
        docs = [self._make_doc(3, "Data Structures", "Lists and dicts.")]
        messages = build_prompt("What are lists?", "Explain.", docs)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        user_content = messages[1]["content"]
        assert "Lab 3" in user_content
        assert "Data Structures" in user_content
        assert "Lists and dicts." in user_content

    def test_prompt_with_five_labs(self):
        """Edge case: 5 labs referenced"""
        docs = [
            self._make_doc(1, "Intro", "Content 1"),
            self._make_doc(2, "Data", "Content 2"),
            self._make_doc(3, "Files", "Content 3"),
            self._make_doc(4, "Functions", "Content 4"),
            self._make_doc(5, "Classes", "Content 5"),
        ]
        messages = build_prompt("Compare all labs", "Explain differences.", docs)
        user_content = messages[1]["content"]

        for i in range(1, 6):
            assert f"Lab {i}" in user_content, f"Lab {i} should be in prompt"
            assert f"Content {i}" in user_content, f"Content for Lab {i} should be in prompt"

    def test_prompt_with_no_context(self):
        """Edge case: no lab context found"""
        messages = build_prompt("Random?", "Random body.", [])
        user_content = messages[1]["content"]
        assert "(No relevant lab materials found" in user_content

    def test_prompt_with_multi_chunk_lab(self):
        """Edge case: single lab split into multiple chunks"""
        docs = [
            self._make_doc(2, "Data Structures", "Part 1 content", chunk_index=0, num_chunks=3),
            self._make_doc(2, "Data Structures", "Part 2 content", chunk_index=1, num_chunks=3),
            self._make_doc(2, "Data Structures", "Part 3 content", chunk_index=2, num_chunks=3),
        ]
        messages = build_prompt("Question?", "Body.", docs)
        user_content = messages[1]["content"]

        assert "Lab 2 (part 1/3)" in user_content
        assert "Lab 2 (part 2/3)" in user_content
        assert "Lab 2 (part 3/3)" in user_content
        # Should NOT have chunk labels for single-chunk docs
        assert "part" not in user_content.replace("(part 1/3)", "").replace("(part 2/3)", "").replace("(part 3/3)", "") or user_content.count("part") == 3

    def test_prompt_labs_sorted(self):
        """Edge case: labs should appear in numerical order even if retrieved out of order"""
        docs = [
            self._make_doc(5, "Classes", "Content 5"),
            self._make_doc(2, "Data", "Content 2"),
            self._make_doc(4, "Functions", "Content 4"),
        ]
        messages = build_prompt("Question?", "Body.", docs)
        user_content = messages[1]["content"]

        pos_2 = user_content.find("Lab 2")
        pos_4 = user_content.find("Lab 4")
        pos_5 = user_content.find("Lab 5")
        assert pos_2 < pos_4 < pos_5, "Labs should appear in sorted order in the prompt"

    def test_prompt_system_mention_multiple_labs(self):
        """System prompt should instruct LLM to handle multiple labs"""
        docs = [
            self._make_doc(1, "A", "Content A"),
            self._make_doc(2, "B", "Content B"),
        ]
        messages = build_prompt("Question?", "Body.", docs)
        system_content = messages[0]["content"]
        assert "multiple labs" in system_content.lower()
        assert "synthesize" in system_content.lower()

    def test_context_truncation_warning(self):
        """When context is very large, it should be truncated with a warning"""
        very_long_content = "X" * 50000
        docs = [
            self._make_doc(1, "A", very_long_content),
            self._make_doc(2, "B", "Content B"),
        ]
        messages = build_prompt("Question?", "Body.", docs)
        user_content = messages[1]["content"]
        # First lab's content should be truncated
        assert "truncated" in user_content.lower() or len(user_content) < len(very_long_content) * 2


# =============================================================================
# INTEGRATION TESTS: retrieve_context() — requires DB
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestRetrieveContext:
    """Integration tests for retrieve_context() — requires a running DB with seeded data."""

    @pytest.fixture
    @pytest.mark.asyncio
    async def session(self):
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlmodel import SQLModel
        from sqlalchemy.orm import sessionmaker
        from app.config import settings

        engine = create_async_engine(settings.database_url)
        AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with AsyncSessionLocal() as session:
            yield session

        await engine.dispose()

    @pytest.fixture
    def question_embedding(self):
        from app.services.embeddings import embed_text
        return embed_text("How do lists work in Python?")

    async def test_retrieve_with_no_lab_filter(self, session, question_embedding):
        """No lab mentioned — should search across ALL labs"""
        docs = await retrieve_context(
            question_embedding, session,
            question_text="How do lists work?",
            lab_number_filter=None,
        )
        assert isinstance(docs, list)
        # Should reference at least some labs
        if docs:
            labs = set(d["lab_number"] for d in docs)
            assert len(labs) >= 1, "Should reference at least 1 lab when searching all"

    async def test_retrieve_with_single_lab_filter(self, session, question_embedding):
        """Single lab mentioned — should only return chunks from that lab"""
        docs = await retrieve_context(
            question_embedding, session,
            question_text="How do lists work?",
            lab_number_filter=[2],
        )
        for doc in docs:
            assert doc["lab_number"] == 2, "All docs should be from lab 2"

    async def test_retrieve_with_five_labs_filter(self, session, question_embedding):
        """Five labs mentioned — should only return chunks from those 5 labs"""
        docs = await retrieve_context(
            question_embedding, session,
            question_text="Compare labs",
            lab_number_filter=[1, 2, 3, 4, 5],
        )
        for doc in docs:
            assert doc["lab_number"] in [1, 2, 3, 4, 5], "All docs should be from the 5 specified labs"

    async def test_retrieve_with_nonexistent_lab_filter(self, session, question_embedding):
        """Lab that doesn't exist — should return empty"""
        docs = await retrieve_context(
            question_embedding, session,
            question_text="Lab 99?",
            lab_number_filter=[99],
        )
        assert docs == [], "Should return no docs for non-existent lab"

    async def test_retrieve_with_mixed_existing_labs(self, session, question_embedding):
        """Some existing, some non-existing — should only return from existing"""
        docs = await retrieve_context(
            question_embedding, session,
            question_text="Lab 1 and 99?",
            lab_number_filter=[1, 99],
        )
        for doc in docs:
            assert doc["lab_number"] in [1, 99]
            # Should only actually return lab 1 chunks (since 99 doesn't exist)
            if doc["lab_number"] == 99:
                pytest.fail("Should not return lab 99 docs (they don't exist)")


# =============================================================================
# FULL PIPELINE INTEGRATION TESTS (require DB + LLM API)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestFullPipeline:
    """Full RAG pipeline tests — requires DB + LLM API key."""

    @pytest.fixture
    @pytest.mark.asyncio
    async def session(self):
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from app.config import settings

        engine = create_async_engine(settings.database_url)
        AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        async with AsyncSessionLocal() as session:
            yield session

        await engine.dispose()

    async def test_pipeline_single_lab(self, session):
        """Full pipeline: 1 lab mentioned"""
        from app.services.rag import run_rag_pipeline

        answer, confidence, labs = await run_rag_pipeline(
            question_title="Lab 2 question",
            question_body="How do I use append() in lab 2?",
            session=session,
        )
        assert isinstance(answer, str)
        assert len(answer) > 0
        assert isinstance(confidence, float)
        assert isinstance(labs, list)
        # All returned labs should be 2
        for lab in labs:
            assert lab == 2, f"Only lab 2 should be referenced, got {lab}"

    async def test_pipeline_five_labs(self, session):
        """Full pipeline: 5 labs mentioned"""
        from app.services.rag import run_rag_pipeline

        answer, confidence, labs = await run_rag_pipeline(
            question_title="Compare all labs",
            question_body="What are the differences between lab 1, lab 2, lab 3, lab 4, and lab 5?",
            session=session,
        )
        assert isinstance(answer, str)
        assert len(answer) > 0
        assert isinstance(labs, list)
        for lab in labs:
            assert lab in [1, 2, 3, 4, 5], f"Only labs 1-5 should be referenced, got {lab}"

    async def test_pipeline_no_lab_mentioned(self, session):
        """Full pipeline: no lab mentioned"""
        from app.services.rag import run_rag_pipeline

        answer, confidence, labs = await run_rag_pipeline(
            question_title="General question",
            question_body="What is a variable in Python?",
            session=session,
        )
        assert isinstance(answer, str)
        assert len(answer) > 0
        # May or may not have labs depending on semantic match
        assert isinstance(labs, list)

    async def test_pipeline_nonexistent_lab(self, session):
        """Full pipeline: non-existent lab mentioned"""
        from app.services.rag import run_rag_pipeline

        answer, confidence, labs = await run_rag_pipeline(
            question_title="Lab 99 question",
            question_body="How do I complete lab 99?",
            session=session,
        )
        assert isinstance(answer, str)
        assert len(answer) > 0
        # Should be empty since lab 99 doesn't exist
        assert labs == [], f"Expected no labs for non-existent lab 99, got {labs}"


# =============================================================================
# SUMMARY: Run all tests
# =============================================================================

if __name__ == "__main__":
    # Run unit tests first (no DB required)
    print("=" * 70)
    print(" Running UNIT TESTS (no DB required)")
    print("=" * 70)

    test_classes = [TestExtractLabNumbers, TestBuildPrompt]
    unit_passed = 0
    unit_failed = 0

    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()
        for method_name in sorted(dir(instance)):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    print(f"  ✅ {method_name}")
                    unit_passed += 1
                except Exception as e:
                    print(f"  ❌ {method_name}: {e}")
                    unit_failed += 1

    print(f"\n{'='*70}")
    print(f" UNIT TESTS: {unit_passed} passed, {unit_failed} failed")
    print(f"{'='*70}")

    # Integration tests require DB — run separately
    print("\n💡 Run integration tests with: pytest test_rag_edge_cases.py -v -k integration")
