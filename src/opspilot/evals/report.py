"""Formats `EvalResult` lists into the "Incident Diagnosis Benchmark" report."""

from __future__ import annotations

from opspilot.evals.runner import EvalResult


def format_report(results: list[EvalResult], *, provider_name: str, check_diagnosis: bool) -> str:
    by_category: dict[str, list[EvalResult]] = {}
    for result in results:
        by_category.setdefault(result.scenario.category, []).append(result)

    mode = "detection + diagnosis" if check_diagnosis else "detection only"
    lines = [f"Incident Diagnosis Benchmark (provider: {provider_name}, {mode})", "", f"{'Category':<10} Accuracy"]

    total_passed = 0
    total_count = 0
    for category in sorted(by_category):
        category_results = by_category[category]
        passed = sum(1 for r in category_results if r.passed)
        count = len(category_results)
        total_passed += passed
        total_count += count
        pct = round(100 * passed / count) if count else 0
        lines.append(f"{category:<10} {pct}% ({passed}/{count})")

    overall_pct = round(100 * total_passed / total_count) if total_count else 0
    lines.append("")
    lines.append(f"{'Overall':<10} {overall_pct}% ({total_passed}/{total_count})")

    failures = [r for r in results if not r.passed]
    if failures:
        lines.append("")
        lines.append("Failures:")
        for result in failures:
            lines.append(f"  - {result.scenario.id}: {'; '.join(result.reasons)}")

    if provider_name == "mock":
        lines.append("")
        if check_diagnosis:
            lines.append(
                "Note: --check-diagnosis was evaluated against the mock provider, which does not "
                "reason — treat diagnosis results as not meaningful."
            )
        else:
            lines.append(
                "Note: diagnosis accuracy not measured (mock provider does not reason). "
                "Run with --provider anthropic|openai --check-diagnosis for a real measurement."
            )
    elif not check_diagnosis:
        lines.append("")
        lines.append("Note: diagnosis accuracy not measured (pass --check-diagnosis to include it).")

    return "\n".join(lines)
