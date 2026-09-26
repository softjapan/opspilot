from pathlib import Path
from unittest.mock import patch

from opspilot.analyzers.base import InvestigationTarget, MySQLTarget
from opspilot.analyzers.mysql import MySQLAnalyzer, parse_slow_log

SAMPLE_SLOW_LOG = """\
# Time: 2024-01-01T12:00:00.000000Z
# User@Host: root[root] @ localhost []
# Query_time: 0.500123  Lock_time: 0.000100 Rows_sent: 1  Rows_examined: 1000
SET timestamp=1704110400;
SELECT * FROM other_table WHERE id = 1;
# Time: 2024-01-01T12:00:05.000000Z
# User@Host: root[root] @ localhost []
# Query_time: 18.241000  Lock_time: 0.000050 Rows_sent: 5  Rows_examined: 68496
SET timestamp=1704110405;
SELECT * FROM m_staff WHERE m_staff_mall_id = 5 AND m_staff_pc_disp = 1;
"""


def test_parse_slow_log_extracts_entries_sorted_by_appearance(tmp_path: Path) -> None:
    log_path = tmp_path / "slow.log"
    log_path.write_text(SAMPLE_SLOW_LOG)

    entries = parse_slow_log(log_path)

    assert len(entries) == 2
    assert entries[0].query_time == 0.500123
    assert entries[0].rows_examined == 1000
    assert entries[1].query_time == 18.241
    assert entries[1].rows_examined == 68496
    assert entries[1].sql == "SELECT * FROM m_staff WHERE m_staff_mall_id = 5 AND m_staff_pc_disp = 1"


REAL_WORLD_SLOW_LOG = """\
mariadbd, Version: 11.8.9-MariaDB-ubu2404-log (mariadb.org binary distribution). started with:
Tcp port: 0  Unix socket: /run/mysqld/mysqld.sock
Time\t\t    Id Command\tArgument
# Time: 260926  7:45:18
# User@Host: root[root] @ localhost []
# Thread_id: 8  Schema: opspilot_demo  QC_hit: No
# Query_time: 0.000016  Lock_time: 0.000000  Rows_sent: 0  Rows_examined: 0
# Rows_affected: 0  Bytes_sent: 11
use `opspilot_demo`;
SET timestamp=1790408718;
SET SESSION long_query_time = 0;
# User@Host: root[root] @ localhost []
# Thread_id: 8  Schema: opspilot_demo  QC_hit: No
# Query_time: 0.007680  Lock_time: 0.000046  Rows_sent: 0  Rows_examined: 70000
# Rows_affected: 0  Bytes_sent: 312
SET timestamp=1790408718;
SELECT * FROM m_staff WHERE m_staff_mall_id = 5 AND m_staff_pc_disp = 1;
mariadbd, Version: 11.8.9-MariaDB-ubu2404-log (mariadb.org binary distribution). started with:
Tcp port: 0  Unix socket: /run/mysqld/mysqld.sock
Time\t\t    Id Command\tArgument
"""


def test_parse_slow_log_handles_real_mariadb_format(tmp_path: Path) -> None:
    """Real logs omit `# Time:` on every entry and interleave restart banners."""
    log_path = tmp_path / "slow.log"
    log_path.write_text(REAL_WORLD_SLOW_LOG)

    entries = parse_slow_log(log_path)

    assert len(entries) == 2
    top = max(entries, key=lambda e: e.query_time)
    assert top.query_time == 0.00768
    assert top.rows_examined == 70000
    assert top.sql == "SELECT * FROM m_staff WHERE m_staff_mall_id = 5 AND m_staff_pc_disp = 1"


def test_parse_slow_log_empty_file_returns_no_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "slow.log"
    log_path.write_text("")

    assert parse_slow_log(log_path) == []


def test_mysql_analyzer_flags_missing_index(tmp_path: Path) -> None:
    log_path = tmp_path / "slow.log"
    log_path.write_text(SAMPLE_SLOW_LOG)

    target = InvestigationTarget(
        name="test",
        mysql=MySQLTarget(slow_log_path=log_path, password="secret"),
    )

    fake_explain_rows = [
        {"table": "m_staff", "type": "ALL", "key": None, "rows": 68496},
    ]

    with patch("opspilot.analyzers.mysql.run_explain", return_value=fake_explain_rows) as mock_explain:
        findings = MySQLAnalyzer().run(target)

    mock_explain.assert_called_once()
    titles = [finding.title for finding in findings]
    assert "Slow query detected" in titles
    assert "Missing index causing full table scan" in titles

    missing_index_finding = next(f for f in findings if f.title == "Missing index causing full table scan")
    assert missing_index_finding.evidence["table"] == "m_staff"


def test_mysql_analyzer_returns_nothing_without_mysql_target() -> None:
    target = InvestigationTarget(name="test")

    assert MySQLAnalyzer().run(target) == []
