"""Linux resource analyzer.

On a real host, reads live CPU/memory/disk usage via `psutil`. For the demo
target, reads a fixed `stats.json` snapshot instead — OpsPilot never SSHes
into or executes anything on a remote host in v1 (read-only, no remote
execution, by design).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import psutil

from opspilot.analyzers.base import Finding, InvestigationTarget

CPU_THRESHOLD_PERCENT = 85.0
MEMORY_THRESHOLD_PERCENT = 85.0
DISK_THRESHOLD_PERCENT = 90.0


def read_stats(stats_path: Path | None) -> dict[str, Any]:
    if stats_path is not None:
        return json.loads(stats_path.read_text(encoding="utf-8"))

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


class LinuxAnalyzer:
    name = "linux"

    def run(self, target: InvestigationTarget) -> list[Finding]:
        if target.linux is None:
            return []

        if target.linux.stats_path is not None and not target.linux.stats_path.exists():
            return []

        stats = read_stats(target.linux.stats_path)
        findings: list[Finding] = []

        if stats.get("cpu_percent", 0) >= CPU_THRESHOLD_PERCENT:
            findings.append(
                Finding(
                    analyzer=self.name,
                    title="High CPU usage",
                    evidence={"cpu_percent": stats["cpu_percent"]},
                    detail="Identify the process consuming CPU, or scale out.",
                )
            )

        if stats.get("memory_percent", 0) >= MEMORY_THRESHOLD_PERCENT:
            findings.append(
                Finding(
                    analyzer=self.name,
                    title="High memory usage",
                    evidence={"memory_percent": stats["memory_percent"]},
                    detail="Check for memory leaks or increase available memory.",
                )
            )

        if stats.get("disk_percent", 0) >= DISK_THRESHOLD_PERCENT:
            findings.append(
                Finding(
                    analyzer=self.name,
                    title="Disk nearly full",
                    evidence={"disk_percent": stats["disk_percent"]},
                    detail="Free up disk space or expand the volume.",
                )
            )

        return findings
