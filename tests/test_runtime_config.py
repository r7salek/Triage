"""Runtime OpenAI configuration tests."""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

from agents.config import DEFAULT_OPENAI_MODEL, resolve_openai_config
from agents.llm import summarize_with_openai


class _FakeResponses:
    def create(self, **kwargs):
        _FakeOpenAI.last_request = kwargs
        return types.SimpleNamespace(output_text="session summary")


class _FakeOpenAI:
    last_api_key = None
    last_request = None

    def __init__(self, api_key: str):
        _FakeOpenAI.last_api_key = api_key
        self.responses = _FakeResponses()


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        _FakeOpenAI.last_api_key = None
        _FakeOpenAI.last_request = None

    def test_resolve_openai_config_prefers_session_values(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key", "OPENAI_MODEL": "env-model"}):
            config = resolve_openai_config(api_key="session-key", model="session-model")

        self.assertEqual(config.api_key, "session-key")
        self.assertEqual(config.model, "session-model")

    def test_resolve_openai_config_preserves_environment_fallback(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key", "OPENAI_MODEL": "env-model"}):
            config = resolve_openai_config()

        self.assertEqual(config.api_key, "env-key")
        self.assertEqual(config.model, "env-model")

    def test_resolve_openai_config_uses_default_model_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            config = resolve_openai_config(api_key="session-key")

        self.assertEqual(config.api_key, "session-key")
        self.assertEqual(config.model, DEFAULT_OPENAI_MODEL)

    def test_summarize_with_openai_uses_session_key_and_model(self):
        fake_openai = types.SimpleNamespace(OpenAI=_FakeOpenAI)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key", "OPENAI_MODEL": "env-model"}):
            with patch.dict(sys.modules, {"openai": fake_openai}):
                summary = summarize_with_openai("prompt", api_key="session-key", model="session-model")

        self.assertEqual(summary, "session summary")
        self.assertEqual(_FakeOpenAI.last_api_key, "session-key")
        self.assertEqual(_FakeOpenAI.last_request["model"], "session-model")
        self.assertEqual(_FakeOpenAI.last_request["input"], "prompt")

    def test_summarize_with_openai_returns_none_without_any_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(summarize_with_openai("prompt"))


if __name__ == "__main__":
    unittest.main()
