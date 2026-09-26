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


def test_redact_evidence_handles_lists_of_strings() -> None:
    evidence = {"matching_lines": ["contact admin@example.com", "no secret here"]}

    redacted = redact_evidence(evidence)

    assert "[REDACTED:email]" in redacted["matching_lines"][0]
    assert redacted["matching_lines"][1] == "no secret here"


def test_redact_text_does_not_flag_long_identifiers_or_row_counts() -> None:
    # A long, purely alphabetic/underscore identifier and a bare long digit
    # run (e.g. a millisecond timestamp) must survive untouched — only
    # digit+letter "secret-shaped" tokens and delimited card numbers count.
    text = "table m_staff_mall_disp_composite_index_column at ts=1758870000000"
    assert redact_text(text) == text


def test_redact_text_masks_api_key_shaped_token() -> None:
    redacted = redact_text("OPSPILOT_ANTHROPIC_MODEL uses key sk-ant-api03-AbCdEf123456789012345678")
    assert "sk-ant-api03-AbCdEf123456789012345678" not in redacted
    assert "[REDACTED:long_secret_like]" in redacted


def test_redact_text_masks_delimited_credit_card() -> None:
    redacted = redact_text("card on file: 4111 1111 1111 1111")
    assert "4111 1111 1111 1111" not in redacted
    assert "[REDACTED:credit_card]" in redacted
