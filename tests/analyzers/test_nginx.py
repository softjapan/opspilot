from pathlib import Path

from opspilot.analyzers.base import InvestigationTarget, NginxTarget
from opspilot.analyzers.nginx import NginxAnalyzer, parse_access_log, parse_error_log

ACCESS_LOG = """\
172.19.0.1 - [26/Sep/2026:10:00:00 +0000] "GET /healthz HTTP/1.1" 200 2 rt=0.001 urt="-"
172.19.0.1 - [26/Sep/2026:10:00:01 +0000] "GET /api/search HTTP/1.1" 502 157 rt=0.003 urt="-"
172.19.0.1 - [26/Sep/2026:10:00:02 +0000] "GET /api/search HTTP/1.1" 502 157 rt=0.002 urt="-"
"""

ERROR_LOG = (
    '2026/09/26 10:00:01 [error] 8#8: *1 connect() failed (111: Connection refused) '
    'while connecting to upstream, client: 172.19.0.1, server: , '
    'request: "GET /api/search HTTP/1.1", upstream: "http://127.0.0.1:9/", host: "localhost"\n'
)


def test_parse_access_log_extracts_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "access.log"
    log_path.write_text(ACCESS_LOG)

    entries = parse_access_log(log_path)

    assert len(entries) == 3
    assert entries[0].status == 200
    assert entries[1].status == 502
    assert entries[1].path == "/api/search"


def test_parse_error_log_extracts_connect_failures(tmp_path: Path) -> None:
    log_path = tmp_path / "error.log"
    log_path.write_text(ERROR_LOG)

    incidents = parse_error_log(log_path)

    assert len(incidents) == 1
    assert incidents[0]["request"] == "GET /api/search HTTP/1.1"
    assert incidents[0]["upstream"] == "http://127.0.0.1:9/"


def test_nginx_analyzer_flags_upstream_failure(tmp_path: Path) -> None:
    access_log = tmp_path / "access.log"
    access_log.write_text(ACCESS_LOG)
    error_log = tmp_path / "error.log"
    error_log.write_text(ERROR_LOG)

    target = InvestigationTarget(
        name="test",
        nginx=NginxTarget(access_log_path=access_log, error_log_path=error_log),
    )

    findings = NginxAnalyzer().run(target)
    titles = [finding.title for finding in findings]

    assert "502 response from upstream" in titles
    assert "Upstream connection failure" in titles

    error_finding = next(f for f in findings if f.title == "502 response from upstream")
    assert error_finding.evidence["occurrences"] == 2


def test_nginx_analyzer_returns_nothing_without_target() -> None:
    assert NginxAnalyzer().run(InvestigationTarget(name="test")) == []


def test_nginx_analyzer_handles_missing_log_files(tmp_path: Path) -> None:
    target = InvestigationTarget(
        name="test",
        nginx=NginxTarget(
            access_log_path=tmp_path / "missing-access.log",
            error_log_path=tmp_path / "missing-error.log",
        ),
    )

    assert NginxAnalyzer().run(target) == []
