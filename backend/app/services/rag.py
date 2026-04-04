"""RAG (Retrieval-Augmented Generation) pipeline.

Takes a question, retrieves relevant lab docs via vector search,
and generates an answer using the LLM API.

Usage:
    from app.services.rag import run_rag_pipeline
    answer, confidence, sources = await run_rag_pipeline(
        question_title="How do lists work?",
        question_body="I don't understand append()",
        session=session,
    )
"""

import httpx
import re
import structlog
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text

from app.config import settings
from app.services.embeddings import embed_text

logger = structlog.get_logger()

# Pipeline constants
TOP_K_DOCS = 3  # Number of lab docs to retrieve
LLM_TIMEOUT = 30.0  # seconds


async def retrieve_context(
    question_embedding: List[float],
    session: AsyncSession,
    top_k: int = TOP_K_DOCS,
) -> List[dict]:
    """Search lab_docs for the most semantically similar content using pgvector.

    Uses cosine distance (<=>) which is built into pgvector.
    Returns top_k documents with their similarity scores.
    """
    # Format embedding as a string for pgvector (e.g., "[0.1, 0.2, ...]")
    embedding_str = str(question_embedding)

    query = text("""
        SELECT id, lab_number, title, content,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM lab_doc
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = await session.execute(query, {
        "embedding": embedding_str,
        "limit": top_k,
    })
    rows = result.fetchall()

    docs = []
    for row in rows:
        docs.append({
            "id": str(row.id),
            "lab_number": row.lab_number,
            "title": row.title,
            "content": row.content,
            "similarity": float(row.similarity),
        })

    logger.info("Retrieved lab docs", count=len(docs), similarities=[d["similarity"] for d in docs])
    return docs


def build_prompt(
    question_title: str,
    question_body: str,
    context_docs: List[dict],
) -> List[dict]:
    """Build the conversation messages for the LLM.

    Returns a list of messages (system + user) ready to be sent to the API.
    """
    system_prompt = """You are a helpful teaching assistant for a programming lab course.
Answer student questions based on the provided lab materials. Be specific and reference the lab content.

Rules:
- If the context contains relevant information, use it to form your answer.
- If the context is NOT relevant, say "I couldn't find relevant lab materials for this question" and give a general answer.
- Always end your response with a confidence score.
- Keep answers concise and practical.

Format your response like this:
ANSWER: <your detailed answer>
CONFIDENCE: <0.0 to 1.0>
"""

    # Build context section from retrieved docs
    context_parts = []
    for doc in context_docs:
        context_parts.append(
            f"### Lab {doc['lab_number']}: {doc['title']}\n{doc['content']}"
        )

    context_section = "\n\n---\n\n".join(context_parts)

    user_prompt = f"""Question: {question_title}

{question_body}

---

Relevant lab materials:

{context_section}
"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def call_llm(messages: List[dict]) -> str:
    """Call the LLM API and return the response text.

    Handles timeouts and network errors gracefully.
    """
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "qwen-turbo",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{settings.llm_api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            logger.error("LLM API timed out", timeout=LLM_TIMEOUT)
            raise
        except httpx.HTTPStatusError as e:
            logger.error("LLM API HTTP error", status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("LLM API call failed", error=str(e))
            raise


def parse_llm_response(response_text: str) -> Tuple[str, float]:
    """Parse the LLM response to extract answer text and confidence score.

    Expected format:
        ANSWER: <text>
        CONFIDENCE: <0.0-1.0>

    Returns:
        (answer_text, confidence_score)
    """
    confidence_match = re.search(r"CONFIDENCE:\s*([0-9.]+)", response_text, re.IGNORECASE)
    confidence = float(confidence_match.group(1)) if confidence_match else 0.5

    # Remove the CONFIDENCE line from the answer
    answer_text = re.sub(
        r"\n?\s*CONFIDENCE:\s*[0-9.]+\s*$",
        "",
        response_text,
        flags=re.IGNORECASE,
    ).strip()

    # Remove "ANSWER:" prefix if present
    answer_text = re.sub(r"^ANSWER:\s*", "", answer_text, flags=re.IGNORECASE).strip()

    return answer_text, confidence


async def run_rag_pipeline(
    question_title: str,
    question_body: str,
    session: AsyncSession,
) -> Tuple[str, float, List[int]]:
    """Run the full RAG pipeline: embed → retrieve → generate.

    Args:
        question_title: The question title.
        question_body: The question body text.
        session: Async database session.

    Returns:
        Tuple of (answer_text, confidence_score, lab_numbers_referenced)
    """
    full_question = f"{question_title}\n\n{question_body}"

    # Step 1: Embed
    logger.info("Embedding question", title=question_title)
    question_embedding = embed_text(full_question)

    # Step 2: Retrieve
    context_docs = await retrieve_context(question_embedding, session)

    if not context_docs:
        logger.warning("No relevant lab docs found")
        return "I couldn't find relevant lab materials for this question. Please ask a TA for help.", 0.0, []

    # Step 3: Build prompt and call LLM
    messages = build_prompt(question_title, question_body, context_docs)
    logger.info("Calling LLM API", docs_count=len(context_docs))

    try:
        response_text = await call_llm(messages)
    except Exception:
        logger.error("LLM call failed, returning fallback answer")
        lab_numbers = [doc["lab_number"] for doc in context_docs]
        return "The AI service is temporarily unavailable. A TA will review your question.", 0.0, lab_numbers

    # Step 4: Parse response
    answer_text, confidence = parse_llm_response(response_text)
    lab_numbers = [doc["lab_number"] for doc in context_docs]

    logger.info(
        "RAG pipeline complete",
        confidence=confidence,
        labs_referenced=lab_numbers,
        answer_length=len(answer_text),
    )

    return answer_text, confidence, lab_numbers
