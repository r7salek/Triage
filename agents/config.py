"""Runtime configuration helpers.

This module resolves optional runtime values from explicit session inputs first,
then environment variables. It intentionally does not persist secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str | None
    model: str


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def resolve_openai_config(api_key: str | None = None, model: str | None = None) -> OpenAIConfig:
    """Resolve OpenAI configuration without writing session secrets to disk."""
    resolved_key = _clean_optional(api_key) or _clean_optional(os.getenv("OPENAI_API_KEY"))
    resolved_model = _clean_optional(model) or _clean_optional(os.getenv("OPENAI_MODEL")) or DEFAULT_OPENAI_MODEL
    return OpenAIConfig(api_key=resolved_key, model=resolved_model)
