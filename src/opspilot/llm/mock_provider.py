"""Deterministic, rule-based fallback provider — no network, no API key.

Used by default so `Finding`s are always visible even without an LLM API
key configured (see `opspilot.llm.factory.get_llm_provider`).

This does not reason about the findings — it picks whichever finding's
evidence shares a keyword with the question (falling back to the last
finding produced), so results are deterministic but not a substitute for a
real LLM's judgment when multiple, unrelated findings are present at once.
"""

from __future__ import annotations

import re

from opspilot.analyzers.base import Finding
from opspilot.llm.base import Explanation

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def _keywords(text: str) -> set[str]:
    return {word.lower() for word in _WORD_RE.findall(text) if len(word) > 3}


def _pick_primary(question: str, findings: list[Finding]) -> Finding:
    question_words = _keywords(question)
    if question_words:
        for finding in findings:
            evidence_text = " ".join(str(value) for value in finding.evidence.values())
            if _keywords(evidence_text) & question_words:
                return finding

    return findings[-1]


class MockLLMProvider:
    def explain(self, question: str, findings: list[Finding]) -> Explanation:
        if not findings:
            return Explanation(
                root_cause="No findings were produced by the analyzers for this target.",
                confidence="LOW",
                recommendation="Widen the investigation window or check that the target is configured correctly.",
            )

        primary = _pick_primary(question, findings)
        confidence = "HIGH" if primary.evidence else "MEDIUM"

        return Explanation(
            root_cause=f"{primary.title} ({primary.analyzer} analyzer).",
            confidence=confidence,
            recommendation=primary.detail
            or "Review the evidence above; no automated recommendation is available for this finding.",
        )
