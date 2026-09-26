"""`opspilot evals run` — the Incident Diagnosis Benchmark."""

from __future__ import annotations

import typer

from opspilot.evals.report import format_report
from opspilot.evals.runner import resolve_provider, run_all
from opspilot.targets import REPO_ROOT

evals_app = typer.Typer(help="Run OpsPilot's evaluation scenarios.")

EVALS_DIR = REPO_ROOT / "evals"


@evals_app.command("run")
def run(
    provider: str = typer.Option("mock", "--provider", help="mock | anthropic | openai"),
    check_diagnosis: bool = typer.Option(
        False,
        "--check-diagnosis",
        help="Also check that the explanation's root cause mentions the expected keywords.",
    ),
) -> None:
    """Run every scenario under evals/ and print a per-category accuracy report."""
    llm_provider = resolve_provider(provider)
    results = run_all(EVALS_DIR, llm_provider=llm_provider, check_diagnosis=check_diagnosis)

    typer.echo(format_report(results, provider_name=provider, check_diagnosis=check_diagnosis))

    if any(not result.passed for result in results):
        raise typer.Exit(code=1)
