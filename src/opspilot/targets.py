"""Built-in investigation targets, shared by the CLI and the API.

Keeping this in one place is what lets `cli/main.py` and `api/main.py` stay
thin wrappers around the same `opspilot.investigate.investigate` call.
"""

from __future__ import annotations

import os
from pathlib import Path

from opspilot.analyzers.base import InvestigationTarget, LinuxTarget, MySQLTarget, NginxTarget

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "demo"


def demo_target() -> InvestigationTarget:
    """The intentionally-broken demo stack (see demo/mariadb-demo).

    Host/port default to the docker-compose port mapping for a CLI running
    on the host; inside the `opspilot-api` container, `OPSPILOT_DEMO_MYSQL_HOST`
    / `_PORT` are overridden to reach `mariadb-demo` directly on the compose
    network.
    """
    return InvestigationTarget(
        name="demo",
        mysql=MySQLTarget(
            slow_log_path=DEMO_DIR / "mariadb-demo" / "logs" / "slow.log",
            host=os.environ.get("OPSPILOT_DEMO_MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("OPSPILOT_DEMO_MYSQL_PORT", "3307")),
            user="root",
            password="opspilot",
            database="opspilot_demo",
        ),
        nginx=NginxTarget(
            access_log_path=DEMO_DIR / "nginx-demo" / "logs" / "access.log",
            error_log_path=DEMO_DIR / "nginx-demo" / "logs" / "error.log",
        ),
        linux=LinuxTarget(stats_path=DEMO_DIR / "linux-demo" / "stats.json"),
    )


def get_target(name: str) -> InvestigationTarget:
    if name == "demo":
        return demo_target()
    raise ValueError(f"Unknown target: {name!r} (only 'demo' is supported so far)")
