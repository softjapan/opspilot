"""Runs eval scenarios against the real `investigate()` pipeline.

MySQL scenarios avoid needing a live database by monkeypatching
`opspilot.analyzers.mysql.run_explain` with the scenario's canned EXPLAIN
rows — the same technique `tests/analyzers/test_mysql.py` uses.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from opspilot.analyzers.base import InvestigationTarget, LinuxTarget, MySQLTarget, NginxTarget
from opspilot.evals.schema import EvalScenario, load_all_scenarios
from opspilot.investigate import investigate
from opspilot.llm.base import LLMProvider


@dataclass
class EvalResult:
    scenario: EvalScenario
    passed: bool
    reasons: list[str] = field(default_factory=list)


def resolve_provider(name: str) -> LLMProvider:
    """Mirrors `opspilot.llm.factory.get_llm_provider`, parameterized instead
    of env-var-based, so evals never need to mutate process environment."""
    if name == "mock":
        from opspilot.llm.mock_provider import MockLLMProvider

        return MockLLMProvider()
    if name == "anthropic":
        from opspilot.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider()
    if name == "openai":
        from opspilot.llm.openai_provider import OpenAILLMProvider

        return OpenAILLMProvider()
    raise ValueError(f"Unknown provider: {name!r} (expected mock/anthropic/openai)")


def _build_target(scenario: EvalScenario, tmp_dir: Path) -> InvestigationTarget:
    mysql_target = None
    if scenario.mysql_fixture is not None:
        slow_log_path = tmp_dir / "slow.log"
        slow_log_path.write_text(scenario.mysql_fixture.slow_log)
        mysql_target = MySQLTarget(
            slow_log_path=slow_log_path, host="eval", port=0, user="eval", password="eval", database="eval"
        )

    nginx_target = None
    if scenario.nginx_fixture is not None:
        access_log_path = tmp_dir / "access.log"
        access_log_path.write_text(scenario.nginx_fixture.access_log)
        error_log_path = tmp_dir / "error.log"
        error_log_path.write_text(scenario.nginx_fixture.error_log)
        nginx_target = NginxTarget(access_log_path=access_log_path, error_log_path=error_log_path)

    linux_target = None
    if scenario.linux_fixture is not None:
        stats_path = tmp_dir / "stats.json"
        stats_path.write_text(json.dumps(scenario.linux_fixture.stats))
        linux_target = LinuxTarget(stats_path=stats_path)

    return InvestigationTarget(name=scenario.id, mysql=mysql_target, nginx=nginx_target, linux=linux_target)


def run_scenario(
    scenario: EvalScenario,
    *,
    llm_provider: LLMProvider,
    check_diagnosis: bool = False,
) -> EvalResult:
    reasons: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        target = _build_target(scenario, Path(tmp))

        explain_patch = (
            patch("opspilot.analyzers.mysql.run_explain", return_value=scenario.mysql_fixture.explain_rows)
            if scenario.mysql_fixture is not None
            else contextlib.nullcontext()
        )

        with explain_patch:
            report = investigate(target, scenario.question, llm_provider=llm_provider)

    finding_titles = {finding.title for finding in report.findings}

    for expected_title in scenario.expect.findings_include:
        if expected_title not in finding_titles:
            reasons.append(f"expected finding '{expected_title}' was not produced")

    for excluded_title in scenario.expect.findings_exclude:
        if excluded_title in finding_titles:
            reasons.append(f"finding '{excluded_title}' should not have been produced")

    if check_diagnosis and scenario.expect.root_cause_keywords:
        lowered = report.root_cause.lower()
        if not any(keyword.lower() in lowered for keyword in scenario.expect.root_cause_keywords):
            reasons.append(
                f"root_cause {report.root_cause!r} did not mention any of {scenario.expect.root_cause_keywords}"
            )

    return EvalResult(scenario=scenario, passed=not reasons, reasons=reasons)


def run_all(
    evals_dir: Path,
    *,
    llm_provider: LLMProvider,
    check_diagnosis: bool = False,
) -> list[EvalResult]:
    scenarios = load_all_scenarios(evals_dir)
    return [run_scenario(s, llm_provider=llm_provider, check_diagnosis=check_diagnosis) for s in scenarios]
