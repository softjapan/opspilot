"""Anthropic Claude-backed explanation provider.

Requires the optional `anthropic` extra: `uv sync --extra anthropic`.
"""

from __future__ import annotations

import json
import os

from opspilot.analyzers.base import Finding
from opspilot.llm.base import Explanation

_SYSTEM_PROMPT = (
    "You are OpsPilot, a production incident investigator. You are given "
    "structured, evidence-based findings produced by deterministic log/DB "
    "analyzers. Never speculate beyond the evidence provided. Respond with "
    "JSON only, matching this shape: "
    '{"root_cause": string, "confidence": "HIGH"|"MEDIUM"|"LOW", "recommendation": string}'
)


class AnthropicLLMProvider:
    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "The 'anthropic' package is not installed. Install it with "
                "`uv sync --extra anthropic`."
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        model = os.environ.get("OPSPILOT_ANTHROPIC_MODEL")
        if not model:
            raise RuntimeError(
                "OPSPILOT_ANTHROPIC_MODEL is not set. Set it to a Claude model id "
                "available to your account."
            )

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def explain(self, question: str, findings: list[Finding]) -> Explanation:
        payload = [
            {
                "analyzer": finding.analyzer,
                "title": finding.title,
                "evidence": finding.evidence,
                "detail": finding.detail,
            }
            for finding in findings
        ]

        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\nFindings: {json.dumps(payload)}",
                }
            ],
        )

        text = "".join(block.text for block in message.content if block.type == "text")
        data = json.loads(text)

        return Explanation(
            root_cause=data["root_cause"],
            confidence=data["confidence"],
            recommendation=data["recommendation"],
        )
