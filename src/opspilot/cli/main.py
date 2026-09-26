"""OpsPilot CLI.

    opspilot investigate --target demo --question "Why is this slow?"
"""

from __future__ import annotations

import typer

from opspilot.analyzers.mysql import is_available as mysql_is_available
from opspilot.cli.evals import evals_app
from opspilot.investigate import Report, investigate
from opspilot.targets import get_target

app = typer.Typer(help="OpsPilot — AI production incident investigator.", no_args_is_help=True)
app.add_typer(evals_app, name="evals")


def _print_report(report: Report) -> None:
    typer.echo("")
    typer.secho("Root cause:", bold=True)
    typer.echo(f"  {report.root_cause}")
    typer.echo("")

    for index, finding in enumerate(report.findings, start=1):
        typer.secho(f"Finding #{index}: {finding.title} (via {finding.analyzer})", bold=True)
        for key, value in finding.evidence.items():
            typer.echo(f"  {key}: {value}")
        typer.echo("")

    typer.secho(f"Confidence: {report.confidence}", bold=True)
    typer.echo("")
    typer.secho("Recommendation:", bold=True)
    typer.echo(f"  {report.recommendation}")


def investigate_(
    target: str = typer.Option("demo", "--target", help="Target to investigate ('demo' only, for now)"),
    question: str = typer.Option("Why is this slow?", "--question", "-q", help="The question to investigate"),
) -> None:
    """Investigate a production issue and print an evidence-based report."""
    try:
        inv_target = get_target(target)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    if inv_target.mysql is not None and not mysql_is_available(inv_target):
        typer.secho(
            f"Demo slow log not found at {inv_target.mysql.slow_log_path}.\n"
            "Run `docker compose up -d` first to start the demo stack.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    def on_progress(step: str) -> None:
        typer.echo(f"✓ {step}")

    try:
        report = investigate(inv_target, question, on_progress=on_progress)
    except Exception as exc:  # noqa: BLE001 - surface any analyzer/LLM failure as a clean CLI error
        typer.echo("")
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    _print_report(report)


@app.command()
def version() -> None:
    """Print the OpsPilot version."""
    typer.echo("opspilot 0.1.0")


app.command(name="investigate")(investigate_)


if __name__ == "__main__":
    app()
