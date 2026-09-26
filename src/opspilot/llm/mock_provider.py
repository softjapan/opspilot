"""Deterministic, rule-based fallback provider — no network, no API key.

Used by default so `Finding`s are always visible even without an LLM API
key configured (see `opspilot.llm.factory.get_llm_provider`).
"""

from __future__ import annotations

from opspilot.analyzers.base import Finding
from opspilot.llm.base import Explanation


class MockLLMProvider:
    def explain(self, question: str, findings: list[Finding]) -> Explanation:
        if not findings:
            return Explanation(
                root_cause="No findings were produced by the analyzers for this target.",
                confidence="LOW",
                recommendation="Widen the investigation window or check that the target is configured correctly.",
            )

        primary = findings[-1] if len(findings) > 1 else findings[0]
        confidence = "HIGH" if primary.evidence else "MEDIUM"

        return Explanation(
            root_cause=f"{primary.title} ({primary.analyzer} analyzer).",
            confidence=confidence,
            recommendation=primary.detail
            or "Review the evidence above; no automated recommendation is available for this finding.",
        )
