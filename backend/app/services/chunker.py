"""Chunking utility for splitting large lab documents into smaller sections.

Splits by markdown heading boundaries (## or ###) or file separators (---),
keeping each chunk under a target size so the RAG context budget can hold
many relevant pieces instead of one monolithic doc.
"""

import re
import structlog

logger = structlog.get_logger()

# Target max chars per chunk.  ~15K chars ≈ 3–4K tokens.
# With MAX_CONTEXT_CHARS = 120K in rag.py this allows ~8 chunks.
MAX_CHUNK_CHARS = 15_000


def chunk_lab_content(content: str, title: str = "") -> list[str]:
    """Split a lab document's content into chunks at natural boundaries.

    Strategy:
    1. If content <= MAX_CHUNK_CHARS → return as single chunk
    2. Split on "## " or "### " heading lines (natural section boundaries)
    3. If a section is still too large, hard-split at MAX_CHUNK_CHARS

    Returns a list of chunk strings (each < MAX_CHUNK_CHARS).
    """
    if len(content) <= MAX_CHUNK_CHARS:
        return [content]

    # Split on level-2 and level-3 markdown headings
    # Keep the heading line with each section
    sections = re.split(r'(\n## )', content)

    # Reassemble sections with their heading prefix
    chunks = []
    current = ""

    for i, part in enumerate(sections):
        if part == '\n## ':
            # This is a separator — prepend to next part
            continue

        # Re-add the heading marker if this part follows a separator
        if i > 0 and sections[i - 1] == '\n## ':
            part = '\n## ' + part

        # If adding this section exceeds limit, flush current chunk first
        if current and len(current) + len(part) > MAX_CHUNK_CHARS:
            chunks.append(current.strip())
            current = ""

        # If this single section is too large, hard-split it
        if len(part) > MAX_CHUNK_CHARS:
            # Flush any accumulated content first
            if current.strip():
                chunks.append(current.strip())
                current = ""
            # Hard-split the oversized section
            chunks.extend(_hard_split(part, MAX_CHUNK_CHARS))
        else:
            if current:
                current += part
            else:
                current = part

    # Flush remaining content
    if current.strip():
        chunks.append(current.strip())

    if len(chunks) > 1:
        logger.info(
            "Content chunked",
            original_chars=len(content),
            num_chunks=len(chunks),
            chunk_sizes=[len(c) for c in chunks],
        )

    return chunks


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Split text into fixed-size pieces when no natural boundary exists."""
    pieces = []
    while len(text) > max_chars:
        # Try to break at a paragraph boundary first
        cut_point = text.rfind('\n\n', 0, max_chars)
        if cut_point == -1:
            cut_point = max_chars

        pieces.append(text[:cut_point].strip())
        text = text[cut_point:].lstrip()

    if text.strip():
        pieces.append(text.strip())
    return pieces
