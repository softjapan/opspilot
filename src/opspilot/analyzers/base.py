"""Shared types for OpsPilot analyzers.

An analyzer inspects one evidence source (MySQL slow log, nginx log, Linux
resource stats, ...) and returns deterministic, evidence-backed `Finding`s.
Analyzers never call an LLM themselves — that happens once, centrally, in
`opspilot.investigate`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class Finding:
    """One piece of evidence produced by an analyzer."""

    analyzer: str
    title: str
    evidence: dict[str, Any] = field(default_factory=dict)
    detail: str = ""


@dataclass
class MySQLTarget:
    slow_log_path: Path
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "opspilot_demo"


@dataclass
class NginxTarget:
    access_log_path: Path
    error_log_path: Path


@dataclass
class LinuxTarget:
    stats_path: Path | None = None
    """When set, read a demo stats.json snapshot instead of the local OS."""


@dataclass
class InvestigationTarget:
    """Bundles the per-analyzer configuration for one investigation."""

    name: str
    mysql: MySQLTarget | None = None
    nginx: NginxTarget | None = None
    linux: LinuxTarget | None = None


class Analyzer(Protocol):
    """An analyzer that knows how to inspect its own evidence source."""

    name: str

    def run(self, target: InvestigationTarget) -> list[Finding]:
        """Return findings for `target`, or an empty list if not applicable."""
        ...
