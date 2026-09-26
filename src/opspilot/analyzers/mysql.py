"""MariaDB/MySQL analyzer: slow query log + EXPLAIN + missing-index rule."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymysql
import pymysql.cursors

from opspilot.analyzers.base import Finding, InvestigationTarget

_STAT_RE = re.compile(
    r"# Query_time:\s*(?P<query_time>[\d.]+)\s+"
    r"Lock_time:\s*(?P<lock_time>[\d.]+)\s+"
    r"Rows_sent:\s*(?P<rows_sent>\d+)\s+"
    r"Rows_examined:\s*(?P<rows_examined>\d+)"
)


@dataclass
class SlowQueryEntry:
    query_time: float
    lock_time: float
    rows_sent: int
    rows_examined: int
    sql: str


def _is_server_banner_line(stripped: str) -> bool:
    """Lines mariadbd prints on (re)start, interleaved with real entries.

    `# Time:` only appears once per second (or is omitted entirely between
    consecutive statements), so entry boundaries are anchored on
    `# Query_time:` instead; these banner lines are the only other
    non-SQL, non-comment text that can appear and must be skipped/reset on.
    """
    return stripped.startswith("mariadbd,") or stripped.startswith("Tcp port:") or "Id Command" in stripped


def parse_slow_log(path: Path) -> list[SlowQueryEntry]:
    """Parse a MariaDB/MySQL slow query log into structured entries.

    Each entry is anchored on its own `# Query_time: ...` line; the SQL text
    is whatever non-comment, non-pragma lines follow it up to the next
    `# Query_time:` line, a server restart banner, or end of file.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    entries: list[SlowQueryEntry] = []
    current_stats: dict[str, float | int] | None = None
    current_sql_lines: list[str] = []

    def flush() -> None:
        if current_stats is None:
            return
        sql = " ".join(current_sql_lines).rstrip(";").strip()
        if not sql:
            return
        entries.append(SlowQueryEntry(sql=sql, **current_stats))  # type: ignore[arg-type]

    for line in lines:
        stripped = line.strip()

        if _is_server_banner_line(stripped):
            flush()
            current_stats = None
            current_sql_lines = []
            continue

        stat_match = _STAT_RE.match(stripped)
        if stat_match:
            flush()
            current_stats = {
                "query_time": float(stat_match["query_time"]),
                "lock_time": float(stat_match["lock_time"]),
                "rows_sent": int(stat_match["rows_sent"]),
                "rows_examined": int(stat_match["rows_examined"]),
            }
            current_sql_lines = []
            continue

        if current_stats is None:
            continue  # not inside an entry yet (e.g. log file header)

        if not stripped or stripped.startswith("#"):
            continue

        upper = stripped.upper()
        if upper.startswith("SET TIMESTAMP") or upper.startswith("USE "):
            continue

        current_sql_lines.append(stripped)

    flush()
    return entries


def run_explain(connection_kwargs: dict[str, Any], sql: str) -> list[dict[str, Any]]:
    """Run `EXPLAIN <sql>` and return the result rows as dicts.

    Isolated as a module-level function so tests can monkeypatch it without
    needing a live database.
    """
    connection = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **connection_kwargs)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN {sql}")
            return list(cursor.fetchall())
    finally:
        connection.close()


class MySQLAnalyzer:
    name = "mysql"

    def run(self, target: InvestigationTarget) -> list[Finding]:
        if target.mysql is None:
            return []

        if not target.mysql.slow_log_path.exists():
            return []

        entries = parse_slow_log(target.mysql.slow_log_path)
        if not entries:
            return []

        entries.sort(key=lambda entry: entry.query_time, reverse=True)
        top = entries[0]

        findings: list[Finding] = [
            Finding(
                analyzer=self.name,
                title="Slow query detected",
                evidence={
                    "query_time": top.query_time,
                    "rows_examined": top.rows_examined,
                    "rows_sent": top.rows_sent,
                    "sql": top.sql,
                },
            )
        ]

        connection_kwargs = {
            "host": target.mysql.host,
            "port": target.mysql.port,
            "user": target.mysql.user,
            "password": target.mysql.password,
            "database": target.mysql.database,
        }

        try:
            explain_rows = run_explain(connection_kwargs, top.sql)
        except Exception as exc:  # noqa: BLE001 - external DB connection is a system boundary
            findings.append(
                Finding(
                    analyzer=self.name,
                    title="EXPLAIN unavailable",
                    evidence={"error": str(exc)},
                    detail="Could not connect to the database to run EXPLAIN on the slow query.",
                )
            )
            return findings

        for row in explain_rows:
            if row.get("type") == "ALL" and row.get("key") is None:
                findings.append(
                    Finding(
                        analyzer=self.name,
                        title="Missing index causing full table scan",
                        evidence={
                            "table": row.get("table"),
                            "type": row.get("type"),
                            "key": row.get("key"),
                            "rows": row.get("rows"),
                        },
                        detail=(
                            "Consider adding a composite index covering the columns "
                            "used in the query's WHERE/JOIN clause."
                        ),
                    )
                )

        return findings
