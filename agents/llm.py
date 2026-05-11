"""Optional OpenAI summarization helpers with deterministic fallback."""

from __future__ import annotations

from typing import Optional

from .config import resolve_openai_config


def summarize_with_openai(prompt: str, api_key: str | None = None, model: str | None = None) -> Optional[str]:
    """Return a short LLM summary when configured, otherwise None."""
    config = resolve_openai_config(api_key=api_key, model=model)
    if not config.api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.api_key)
        response = client.responses.create(
            model=config.model,
            input=prompt,
            max_output_tokens=700,
        )
        return getattr(response, "output_text", None)
    except Exception:
        return None
