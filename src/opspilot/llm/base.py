"""Pluggable LLM provider interface.

A provider only ever *explains* findings that analyzers already produced —
it never chooses what to investigate or executes anything.
"""

from __future__ import annotations

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
