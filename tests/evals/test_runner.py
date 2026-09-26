from pathlib import Path

from opspilot.evals.runner import resolve_provider, run_all, run_scenario
from opspilot.evals.schema import EvalScenario, ExpectedOutcome, NginxFixture, load_scenario
from opspilot.targets import REPO_ROOT

EVALS_DIR = REPO_ROOT / "evals"


def test_load_scenario_parses_mysql_fixture(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        """
id: test-scenario
category: mysql
description: test
question: "why?"
fixtures:
  mysql:
    slow_log: "some log"
    explain_rows:
      - table: m_staff
        type: ALL
        key: null
expect:
  findings_include: ["Missing index causing full table scan"]
"""
    )

    scenario = load_scenario(scenario_path)

    assert scenario.id == "test-scenario"
    assert scenario.mysql_fixture is not None
    assert scenario.mysql_fixture.explain_rows[0]["table"] == "m_staff"
    assert scenario.expect.findings_include == ["Missing index causing full table scan"]


def test_run_scenario_mysql_missing_index_passes() -> None:
    scenario = load_scenario(EVALS_DIR / "mysql" / "missing-index.yaml")

    result = run_scenario(scenario, llm_provider=resolve_provider("mock"))

    assert result.passed, result.reasons


def test_run_scenario_reports_missing_expected_finding() -> None:
    scenario = EvalScenario(
        id="broken-expectation",
        category="nginx",
        description="",
        question="q",
        expect=ExpectedOutcome(findings_include=["Something that will never happen"]),
        nginx_fixture=NginxFixture(access_log="", error_log=""),
    )

    result = run_scenario(scenario, llm_provider=resolve_provider("mock"))

    assert not result.passed
    assert "Something that will never happen" in result.reasons[0]


def test_all_shipped_scenarios_pass_in_detection_mode() -> None:
    """Regression check: eval fixtures must stay in sync with analyzer behavior."""
    results = run_all(EVALS_DIR, llm_provider=resolve_provider("mock"), check_diagnosis=False)

    failures = [(r.scenario.id, r.reasons) for r in results if not r.passed]
    assert not failures, failures
    assert len(results) == 6
