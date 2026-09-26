from opspilot.redact.patterns import redact_evidence, redact_text


def test_redact_text_masks_email() -> None:
    assert "[REDACTED:email]" in redact_text("contact admin@example.com for help")


def test_redact_text_masks_password_param() -> None:
    redacted = redact_text("mysql://user:pw@host/db?password=hunter2")
    assert "hunter2" not in redacted
    assert "[REDACTED:password_param]" in redacted


def test_redact_text_masks_bearer_token() -> None:
    redacted = redact_text("Authorization: Bearer abcdef123456")
    assert "abcdef123456" not in redacted
    assert "[REDACTED:bearer_token]" in redacted


def test_redact_text_leaves_short_sql_untouched() -> None:
    sql = "SELECT * FROM m_staff WHERE m_staff_mall_id = 5"
    assert redact_text(sql) == sql


def test_redact_evidence_handles_nested_dicts_and_non_strings() -> None:
    evidence = {
        "query_time": 18.241,
        "rows_examined": 68496,
        "detail": {"contact": "someone@example.com"},
    }

    redacted = redact_evidence(evidence)

    assert redacted["query_time"] == 18.241
    assert redacted["rows_examined"] == 68496
    assert "[REDACTED:email]" in redacted["detail"]["contact"]
