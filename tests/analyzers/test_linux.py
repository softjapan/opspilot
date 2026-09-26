import json
from pathlib import Path

from opspilot.analyzers.base import InvestigationTarget, LinuxTarget
from opspilot.analyzers.linux import LinuxAnalyzer


def _write_stats(tmp_path: Path, **stats: float) -> Path:
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(json.dumps(stats))
    return stats_path


def test_linux_analyzer_flags_high_usage(tmp_path: Path) -> None:
    stats_path = _write_stats(tmp_path, cpu_percent=96.4, memory_percent=91.2, disk_percent=88.7)
    target = InvestigationTarget(name="test", linux=LinuxTarget(stats_path=stats_path))

    findings = LinuxAnalyzer().run(target)
    titles = {finding.title for finding in findings}

    assert "High CPU usage" in titles
    assert "High memory usage" in titles
    assert "Disk nearly full" not in titles  # 88.7 is below the 90.0 threshold


def test_linux_analyzer_returns_nothing_when_below_thresholds(tmp_path: Path) -> None:
    stats_path = _write_stats(tmp_path, cpu_percent=10.0, memory_percent=20.0, disk_percent=30.0)
    target = InvestigationTarget(name="test", linux=LinuxTarget(stats_path=stats_path))

    assert LinuxAnalyzer().run(target) == []


def test_linux_analyzer_returns_nothing_without_target() -> None:
    assert LinuxAnalyzer().run(InvestigationTarget(name="test")) == []


def test_linux_analyzer_handles_missing_stats_file(tmp_path: Path) -> None:
    target = InvestigationTarget(name="test", linux=LinuxTarget(stats_path=tmp_path / "missing.json"))

    assert LinuxAnalyzer().run(target) == []
