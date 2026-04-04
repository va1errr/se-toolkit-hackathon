"""Message transformations: cache_control tagging."""

from __future__ import annotations

from typing import Any


def _add_cache_control(message: dict[str, Any]) -> dict[str, Any]:
    """Add cache_control to the last content item of a message."""
    content = message.get("content")

    if isinstance(content, str):
        return {
            **message,
            "content": [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }

    if isinstance(content, list) and content:
        new_parts: list[Any] = [*content]
        last: Any = new_parts[-1]
        if isinstance(last, dict):
            new_parts[-1] = {**last, "cache_control": {"type": "ephemeral"}}
        return {**message, "content": new_parts}

    return message


def transform_messages(
    messages: list[dict[str, Any]],
    model: str,
    *,
    streaming: bool = False,
) -> list[dict[str, Any]]:
    """Add cache_control matching the real client.

    Streaming: cache_control on system message + last message.
    Non-streaming: cache_control on system message only.
    """
    transformed = list(messages)

    sys_idx = next(
        (i for i, m in enumerate(transformed) if m.get("role") == "system"), None
    )

    # DashScope API requires a system message to be present
    if sys_idx is None:
        transformed.insert(0, {"role": "system", "content": ""})
        sys_idx = 0

    # Apply cache_control to system message (always) and last message (streaming only)
    if sys_idx is not None:
        transformed[sys_idx] = _add_cache_control(transformed[sys_idx])

    if streaming and transformed:
        last_idx = len(transformed) - 1
        if last_idx != sys_idx:
            transformed[last_idx] = _add_cache_control(transformed[last_idx])

    return transformed
