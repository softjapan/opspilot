"""nginx analyzer: access/error log parsing + upstream failure detection.

Expects the custom `opspilot` log_format defined in demo/nginx-demo/nginx.conf:

    log_format opspilot '$remote_addr - [$time_local] "$request" $status '
                         '$body_bytes_sent rt=$request_time urt="$upstream_response_time"';
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from opspilot.analyzers.base import Finding, InvestigationTarget

_ACCESS_RE = re.compile(
    r'^(?P<remote_addr>\S+) - \[(?P<time_local>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) \S+" '
    r'(?P<status>\d{3}) (?P<bytes>\d+) '
    r'rt=(?P<request_time>[\d.]+) urt="(?P<upstream_time>[^"]*)"'
)

_ERROR_KEYWORDS = ("connect() failed", "upstream timed out", "no live upstreams")
_REQUEST_RE = re.compile(r'request: "([^"]*)"')
_UPSTREAM_RE = re.compile(r'upstream: "([^"]*)"')

SLOW_REQUEST_THRESHOLD_SECONDS = 1.0


@dataclass
class AccessLogEntry:
    method: str
    path: str
    status: int
    request_time: float


def parse_access_log(path: Path) -> list[AccessLogEntry]:
    entries: list[AccessLogEntry] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _ACCESS_RE.search(line)
        if not match:
            continue
        entries.append(
            AccessLogEntry(
                method=match["method"],
                path=match["path"],
                status=int(match["status"]),
                request_time=float(match["request_time"]),
            )
        )
    return entries


def parse_error_log(path: Path) -> list[dict[str, str]]:
    incidents: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not any(keyword in line for keyword in _ERROR_KEYWORDS):
            continue
        request_match = _REQUEST_RE.search(line)
        upstream_match = _UPSTREAM_RE.search(line)
        incidents.append(
            {
                "message": line.strip(),
                "request": request_match.group(1) if request_match else "",
                "upstream": upstream_match.group(1) if upstream_match else "",
            }
        )
    return incidents


class NginxAnalyzer:
    name = "nginx"

    def run(self, target: InvestigationTarget) -> list[Finding]:
        if target.nginx is None:
            return []

        findings: list[Finding] = []

        if target.nginx.access_log_path.exists():
            entries = parse_access_log(target.nginx.access_log_path)

            error_entries = [entry for entry in entries if entry.status >= 500]
            if error_entries:
                # Report the most frequent status code, not just whichever
                # happened to be logged first — a single transient 500
                # shouldn't overshadow a systematic run of 502s.
                dominant_status, dominant_count = Counter(entry.status for entry in error_entries).most_common(1)[0]
                representative = next(entry for entry in error_entries if entry.status == dominant_status)
                findings.append(
                    Finding(
                        analyzer=self.name,
                        title=f"{dominant_status} response from upstream",
                        evidence={
                            "method": representative.method,
                            "path": representative.path,
                            "status": dominant_status,
                            "occurrences": dominant_count,
                        },
                        detail="Check that the upstream service behind this route is running and reachable from nginx.",
                    )
                )

            slow_entries = [entry for entry in entries if entry.request_time >= SLOW_REQUEST_THRESHOLD_SECONDS]
            if slow_entries:
                slowest = max(slow_entries, key=lambda entry: entry.request_time)
                findings.append(
                    Finding(
                        analyzer=self.name,
                        title="Slow upstream response",
                        evidence={"path": slowest.path, "request_time": slowest.request_time},
                    )
                )

        if target.nginx.error_log_path.exists():
            incidents = parse_error_log(target.nginx.error_log_path)
            if incidents:
                first = incidents[0]
                findings.append(
                    Finding(
                        analyzer=self.name,
                        title="Upstream connection failure",
                        evidence={"message": first["message"], "upstream": first["upstream"]},
                        detail="Check that the upstream service is running and reachable from nginx.",
                    )
                )

        return findings
