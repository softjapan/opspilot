"""Orchestrates one investigation: analyzers -> redaction -> LLM explanation.

Shared by the CLI and (from Week 3) the API, so the two surfaces never
duplicate this logic.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from opspilot.analyzers.base import Analyzer, Finding, InvestigationTarget
from opspilot.analyzers.linux import LinuxAnalyzer
from opspilot.analyzers.mysql import MySQLAnalyzer
from opspilot.analyzers.nginx import NginxAnalyzer
from opspilot.llm.base import Explanation, LLMProvider
from opspilot.llm.factory import get_llm_provider
from opspilot.redact.patterns import redact_evidence

DEFAULT_ANALYZERS: list[Analyzer] = [MySQLAnalyzer(), NginxAnalyzer(), LinuxAnalyzer()]

ProgressCallback = Callable[[str], None]


@dataclass
class Report:
    question: str
    findings: list[Finding]
    root_cause: str
    confidence: str
    recommendation: str


def investigate(
    target: InvestigationTarget,
    question: str,
    *,
    analyzers: Iterable[Analyzer] | None = None,
    llm_provider: LLMProvider | None = None,
    on_progress: ProgressCallback | None = None,
) -> Report:
    """Run all analyzers against `target`, then have an LLM explain the findings.

    `findings` on the returned `Report` are unredacted — they are only ever
    displayed locally (CLI/Web UI). Redaction applies solely to the payload
    sent to the LLM provider.
    """
    analyzers = list(analyzers) if analyzers is not None else DEFAULT_ANALYZERS
    provider = llm_provider or get_llm_provider()

    all_findings: list[Finding] = []
    for analyzer in analyzers:
        if on_progress:
            on_progress(f"Analyzing {analyzer.name}")
        all_findings.extend(analyzer.run(target))

    redacted_findings = [
        Finding(
            analyzer=finding.analyzer,
            title=finding.title,
            evidence=redact_evidence(finding.evidence),
            detail=finding.detail,
        )
        for finding in all_findings
    ]

    if on_progress:
        on_progress("Generating explanation")
    explanation: Explanation = provider.explain(question, redacted_findings)

    return Report(
        question=question,
        findings=all_findings,
        root_cause=explanation.root_cause,
        confidence=explanation.confidence,
        recommendation=explanation.recommendation,
    )
