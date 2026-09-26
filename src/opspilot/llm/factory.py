"""Selects an `LLMProvider` from the `OPSPILOT_LLM_PROVIDER` env var.

Defaults to the mock provider so findings are always visible without an
API key configured.
"""

from __future__ import annotations

import os

from opspilot.llm.base import LLMProvider
from opspilot.llm.mock_provider import MockLLMProvider


def get_llm_provider() -> LLMProvider:
    provider_name = os.environ.get("OPSPILOT_LLM_PROVIDER", "mock").lower()

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "anthropic":
        from opspilot.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider()

    if provider_name == "openai":
        from opspilot.llm.openai_provider import OpenAILLMProvider

        return OpenAILLMProvider()

    raise ValueError(f"Unknown OPSPILOT_LLM_PROVIDER: {provider_name!r} (expected mock/anthropic/openai)")
