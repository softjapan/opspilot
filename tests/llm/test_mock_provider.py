from opspilot.analyzers.base import Finding
from opspilot.llm.mock_provider import MockLLMProvider


def test_mock_provider_with_no_findings() -> None:
    explanation = MockLLMProvider().explain("Why is this slow?", [])

    assert explanation.confidence == "LOW"
    assert "No findings" in explanation.root_cause


def test_mock_provider_prefers_the_most_specific_finding() -> None:
    findings = [
        Finding(analyzer="mysql", title="Slow query detected", evidence={"query_time": 18.2}),
        Finding(
            analyzer="mysql",
            title="Missing index causing full table scan",
            evidence={"table": "m_staff"},
            detail="Add a composite index.",
        ),
    ]

    explanation = MockLLMProvider().explain("Why is this slow?", findings)

    assert "Missing index" in explanation.root_cause
    assert explanation.confidence == "HIGH"
    assert explanation.recommendation == "Add a composite index."


def test_mock_provider_is_deterministic() -> None:
    findings = [Finding(analyzer="mysql", title="Slow query detected", evidence={"query_time": 18.2})]

    first = MockLLMProvider().explain("q", findings)
    second = MockLLMProvider().explain("q", findings)

    assert first == second
