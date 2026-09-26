"""Eval scenario schema + YAML loading.

A scenario supplies fixed fixtures for one or more analyzers (no live
MariaDB/nginx/host needed) and the expected findings/diagnosis, so the same
`investigate()` pipeline the CLI/API use can be exercised deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MySQLFixture:
    slow_log: str
    explain_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NginxFixture:
    access_log: str = ""
    error_log: str = ""


@dataclass
class LinuxFixture:
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpectedOutcome:
    findings_include: list[str] = field(default_factory=list)
    findings_exclude: list[str] = field(default_factory=list)
    root_cause_keywords: list[str] = field(default_factory=list)


@dataclass
class EvalScenario:
    id: str
    category: str
    description: str
    question: str
    expect: ExpectedOutcome
    mysql_fixture: MySQLFixture | None = None
    nginx_fixture: NginxFixture | None = None
    linux_fixture: LinuxFixture | None = None


def load_scenario(path: Path) -> EvalScenario:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    fixtures = data.get("fixtures", {})

    mysql_fixture = None
    if "mysql" in fixtures:
        mysql_data = fixtures["mysql"]
        mysql_fixture = MySQLFixture(
            slow_log=mysql_data["slow_log"],
            explain_rows=mysql_data.get("explain_rows", []),
        )

    nginx_fixture = None
    if "nginx" in fixtures:
        nginx_data = fixtures["nginx"]
        nginx_fixture = NginxFixture(
            access_log=nginx_data.get("access_log", ""),
            error_log=nginx_data.get("error_log", ""),
        )

    linux_fixture = None
    if "linux" in fixtures:
        linux_fixture = LinuxFixture(stats=fixtures["linux"].get("stats", {}))

    expect_data = data.get("expect", {})
    expect = ExpectedOutcome(
        findings_include=expect_data.get("findings_include", []),
        findings_exclude=expect_data.get("findings_exclude", []),
        root_cause_keywords=expect_data.get("root_cause_keywords", []),
    )

    return EvalScenario(
        id=data["id"],
        category=data["category"],
        description=data.get("description", ""),
        question=data["question"],
        expect=expect,
        mysql_fixture=mysql_fixture,
        nginx_fixture=nginx_fixture,
        linux_fixture=linux_fixture,
    )


def load_all_scenarios(evals_dir: Path) -> list[EvalScenario]:
    return [load_scenario(path) for path in sorted(evals_dir.glob("*/*.yaml"))]
