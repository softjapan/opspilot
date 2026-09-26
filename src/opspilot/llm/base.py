"""Pluggable LLM provider interface.

A provider only ever *explains* findings that analyzers already produced —
it never chooses what to investigate or executes anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol

from opspilot.analyzers.base import Finding

Confidence = Literal["HIGH", "MEDIUM", "LOW"]


@dataclass
class Explanation:
    root_cause: str
    confidence: Confidence
    recommendation: str


class LLMProvider(Protocol):
    def explain(self, question: str, findings: list[Finding]) -> Explanation:
        """Turn evidence-backed findings into a natural-language explanation."""
        ...


def _strip_code_fence(text: str) -> str:
    """Models frequently wrap JSON in ```json ... ``` despite instructions not to."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_explanation_json(text: str, *, source: str) -> Explanation:
    """Parse a provider's raw text response into an `Explanation`.

    Tolerates markdown code fences and raises a clear `RuntimeError` (including
    the raw response) on malformed or incomplete JSON, instead of letting a
    bare `json.JSONDecodeError`/`KeyError` propagate.
    """
    cleaned = _strip_code_fence(text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{source} response was not valid JSON: {text!r}") from exc

    try:
        return Explanation(
            root_cause=data["root_cause"],
            confidence=data["confidence"],
            recommendation=data["recommendation"],
        )
    except KeyError as exc:
        raise RuntimeError(f"{source} response JSON is missing key {exc}: {data!r}") from exc
