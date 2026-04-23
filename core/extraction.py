"""Structured LLM extraction using Instructor.

Provides a reusable wrapper around Instructor's OpenAI client patching,
returning validated Pydantic models from natural-language text.
"""

from __future__ import annotations

import threading
from typing import TypeVar

import instructor
from openai import OpenAI
from pydantic import BaseModel

from core.exceptions import ExtractionError

T = TypeVar("T", bound=BaseModel)

_client: instructor.Instructor | None = None
_client_lock = threading.Lock()


def create_instructor_client(
    *,
    openai_client: OpenAI | None = None,
    mode: instructor.Mode = instructor.Mode.TOOLS,
) -> instructor.Instructor:
    """Create an Instructor-patched OpenAI client.

    Args:
        openai_client: Optional pre-configured OpenAI client.
            Defaults to a new ``OpenAI()`` instance.
        mode: Instructor extraction mode. Defaults to TOOLS
            (OpenAI function-calling).

    Returns:
        Patched client ready for structured extraction.
    """
    base_client = openai_client or OpenAI()
    return instructor.from_openai(base_client, mode=mode)


def _get_client() -> instructor.Instructor:
    """Return a cached Instructor client, creating it on first call."""
    global _client  # noqa: PLW0603
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = create_instructor_client()
    return _client


def extract(
    text: str,
    response_model: type[T],
    *,
    model: str = "gpt-4o-mini",
    max_retries: int = 2,
) -> T:
    """Extract structured data from text using an LLM.

    Args:
        text: Natural-language input to extract from.
        response_model: Pydantic model class defining the output schema.
        model: OpenAI model to use for extraction.
        max_retries: Number of retries on validation failure.

    Returns:
        Validated instance of ``response_model``.

    Raises:
        ExtractionError: If extraction or validation fails.
    """
    client = _get_client()
    try:
        return client.chat.completions.create(
            model=model,
            response_model=response_model,
            max_retries=max_retries,
            messages=[
                {
                    "role": "user",
                    "content": text,
                },
            ],
        )
    except Exception as exc:
        raise ExtractionError(
            f"Extraction failed for {response_model.__name__}: {exc}",
            details={"model": model, "text_length": len(text)},
        ) from exc
