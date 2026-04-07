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
SIMILARITY_THRESHOLD = 0.25  # Min cosine similarity for a chunk to be included
STRONG_MATCH_THRESHOLD = 0.35  # Above this, chunks are likely relevant
MAX_DOCS = 20                # Upper bound on chunks to retrieve
LLM_TIMEOUT = 120.0  # seconds
MAX_CONTEXT_CHARS = 120_000  # Max total context chars (~25K tokens) to avoid upstream 400 errors


def extract_lab_numbers(question_text: str) -> list[int]:
    """Extract all explicit lab numbers from question (e.g., 'lab 4 and 5' → [4, 5])."""
    return sorted(set(
        int(m) for m in re.findall(r'\blab\s*#?(\d+)\b', question_text, re.IGNORECASE)
    ))


async def retrieve_context(
    question_embedding: List[float],
    session: AsyncSession,
    top_k: int = MAX_DOCS,
    question_text: str = "",
    lab_number_filter: List[int] | None = None,
) -> List[dict]:
    """Search lab_docs for the most semantically similar content using pgvector.

    If lab_number_filter is provided (extracted from the question), the query
    prioritizes those specific labs — semantic search runs within the filtered set
    so that "Lab 1" questions get Lab 1 content, not Lab 5's Git section.

    Returns documents with their similarity scores.
    """
    # Format embedding as a string for pgvector (e.g., "[0.1, 0.2, ...]")
    embedding_str = str(question_embedding)

    # Build query — filter by lab_number if explicitly mentioned in question
    if lab_number_filter:
        lab_placeholders = ", ".join(f":lab_{i}" for i in range(len(lab_number_filter)))
        where_clause = f"WHERE lab_number IN ({lab_placeholders})"
        params = {
            "embedding": embedding_str,
            "limit": top_k,
            **{f"lab_{i}": ln for i, ln in enumerate(lab_number_filter)},
        }
        logger.info("Retrieving with lab number filter", labs=lab_number_filter)
    else:
        where_clause = ""
        params = {"embedding": embedding_str, "limit": top_k}

    query = text(f"""
        SELECT id, lab_number, title, content, chunk_index, num_chunks,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM lab_doc
        {where_clause}
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)
    result = await session.execute(query, params)
    rows = result.fetchall()

    docs = []
    for row in rows:
        sim = float(row.similarity)
        # When a lab filter was applied, accept all chunks from the filtered labs
        # (the user explicitly asked about these labs — don't filter by similarity).
        # When no filter, use the strict threshold to avoid irrelevant context.
        if lab_number_filter or sim >= STRONG_MATCH_THRESHOLD:
            docs.append({
                "id": str(row.id),
                "lab_number": row.lab_number,
                "title": row.title,
                "content": row.content,
                "similarity": sim,
                "chunk_index": row.chunk_index,
                "num_chunks": row.num_chunks,
            })

    logger.info(
        "Retrieved lab doc chunks",
        count=len(docs),
        labs_referenced=sorted(set(d["lab_number"] for d in docs)),
        similarities=[round(d["similarity"], 3) for d in docs],
        chunk_indices=[d["chunk_index"] for d in docs],
    )
    return docs


def build_prompt(
    question_title: str,
    question_body: str,
    context_docs: List[dict],
) -> List[dict]:
    """Build the conversation messages for the LLM.

    Returns a list of messages (system + user) ready to be sent to the API.
    Context docs are truncated if they exceed MAX_CONTEXT_CHARS.
    """
    system_prompt = """You are a helpful teaching assistant for a programming lab course.
Answer student questions based on the provided lab materials when possible.

Rules:
- If the context contains relevant information, use it to form your answer and cite the lab number(s).
- When multiple labs are provided, synthesize across them — explain how concepts evolve from lab to lab.
- If the context is NOT relevant or doesn't help, answer from your general programming knowledge. Clearly state "This is not covered in the lab materials, but here's what I know:" before your answer.
- Always end your response with a confidence score between 0.0 and 1.0.
- Keep answers clear, practical, and example-driven.

Format your response like this:
ANSWER: <your detailed answer>
CONFIDENCE: <0.0 to 1.0>
"""

    # Group chunks by lab_number, preserving similarity order
    lab_groups: dict[int, list[dict]] = {}
    for doc in context_docs:
        lab_groups.setdefault(doc["lab_number"], []).append(doc)

    # Build context section from grouped chunks, respecting size limit
    chunk_parts = []
    total_chars = 0
    separator = "\n\n---\n\n"

    for lab_num in sorted(lab_groups.keys()):
        lab_chunks = lab_groups[lab_num]
        lab_title = lab_chunks[0].get("title", f"Lab {lab_num}")

        for chunk in lab_chunks:
            chunk_label = (
                f" (part {chunk['chunk_index'] + 1}/{chunk['num_chunks']})"
                if chunk.get("num_chunks", 1) > 1
                else ""
            )
            header = f"### Lab {lab_num}{chunk_label}: {lab_title}\n"
            content = chunk['content']
            doc_chars = len(header) + len(content) + len(separator)

            if total_chars + doc_chars > MAX_CONTEXT_CHARS:
                remaining = MAX_CONTEXT_CHARS - total_chars
                if remaining > 500:
                    truncated_content = content[:remaining - len(header) - 50] + "\n\n...(content truncated due to size limit)"
                    chunk_parts.append(header + truncated_content)
                    logger.warning(
                        "Context truncated due to size limit",
                        total_chars=total_chars,
                        lab=lab_num,
                    )
                total_chars = MAX_CONTEXT_CHARS  # Signal we're full
                break

            chunk_parts.append(header + content)
            total_chars += doc_chars

        if total_chars >= MAX_CONTEXT_CHARS:
            break

    context_section = separator.join(chunk_parts)

    user_prompt = f"""Question: {question_title}

{question_body}

---

Relevant lab materials:

{context_section if context_section else "(No relevant lab materials found — answer from your general knowledge.)"}
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
        "model": "coder-model",  # Matches qwen-code-api proxy default
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
    # Extract explicit lab number mentions from the question text
    mentioned_labs = extract_lab_numbers(full_question)

    context_docs = await retrieve_context(
        question_embedding, session,
        question_text=full_question,
        lab_number_filter=mentioned_labs or None,
    )

    # Step 2b: If no chunks strongly match, discard context so the LLM answers from general knowledge
    if context_docs:
        max_sim = max(d["similarity"] for d in context_docs)
        if max_sim < STRONG_MATCH_THRESHOLD and not mentioned_labs:
            # Only skip context if no explicit lab was mentioned
            logger.info(
                "No strong matches — answering from general knowledge",
                max_similarity=round(max_sim, 3),
                chunk_count=len(context_docs),
            )
            context_docs = []
        elif context_docs:
            logger.info("Matches found — using lab context", max_similarity=round(max_sim, 3))
        else:
            logger.info("Lab filter applied but no chunks matched threshold — answering from general knowledge")
            context_docs = []
    else:
        if mentioned_labs:
            logger.warning(
                "No matching chunks for explicitly mentioned labs",
                labs=mentioned_labs,
            )
        else:
            logger.info("No relevant lab docs found — answering from general knowledge")

    # Step 3: Build prompt and call LLM (always call it, even with empty context)
    messages = build_prompt(question_title, question_body, context_docs)
    logger.info("Calling LLM API", docs_count=len(context_docs))

    try:
        response_text = await call_llm(messages)
    except httpx.TimeoutException:
        logger.error("LLM API timed out", timeout=LLM_TIMEOUT)
        lab_numbers = [doc["lab_number"] for doc in context_docs] if context_docs else []
        return "⚠️ The AI service timed out. A TA will review your question.", 0.0, lab_numbers
    except httpx.HTTPStatusError as e:
        logger.error("LLM API HTTP error", status=e.response.status_code)
        lab_numbers = [doc["lab_number"] for doc in context_docs] if context_docs else []
        return f"⚠️ The AI service returned an error ({e.response.status_code}). A TA will review your question.", 0.0, lab_numbers
    except Exception as e:
        logger.error("LLM call failed", error=str(e))
        lab_numbers = [doc["lab_number"] for doc in context_docs] if context_docs else []
        return f"⚠️ The AI service encountered an unexpected error ({type(e).__name__}). A TA will review your question.", 0.0, lab_numbers

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
