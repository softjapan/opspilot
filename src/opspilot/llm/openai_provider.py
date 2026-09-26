"""OpenAI-backed explanation provider.

Requires the optional `openai` extra: `uv sync --extra openai`.
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


class OpenAILLMProvider:
    def __init__(self) -> None:
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is not installed. Install it with "
                "`uv sync --extra openai`."
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        model = os.environ.get("OPSPILOT_OPENAI_MODEL")
        if not model:
            raise RuntimeError(
                "OPSPILOT_OPENAI_MODEL is not set. Set it to an OpenAI model id "
                "available to your account."
            )

        self._client = openai.OpenAI(api_key=api_key)
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

        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Question: {question}\nFindings: {json.dumps(payload)}",
                },
            ],
        )

        data = json.loads(response.choices[0].message.content)

        return Explanation(
            root_cause=data["root_cause"],
            confidence=data["confidence"],
            recommendation=data["recommendation"],
        )
