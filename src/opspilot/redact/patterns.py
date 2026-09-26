"""Redact likely-sensitive substrings before evidence is sent to an LLM.

This is a coarse, regex-based safety net — not a guarantee of perfect
detection. It only gates what leaves the machine towards an LLM provider;
local CLI/API/Web display of evidence is unaffected (see
`opspilot.investigate`).
"""

from __future__ import annotations

import re
from typing import Any

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    (
        "password_param",
        re.compile(r"(?i)\b(password|passwd|pwd)\s*=\s*[^&\s\"']+"),
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\b(bearer|token)\s+[A-Za-z0-9._-]{8,}"),
    ),
    # Requires explicit group delimiters (as real, screen-formatted card
    # numbers almost always have) so a bare digit run — a timestamp, a row
    # count, an id — isn't mistaken for one.
    ("credit_card", re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{1,7}\b")),
    # Catch-all for API-key-shaped strings: long, and mixing letters with at
    # least one digit (typical of tokens/hashes) — excludes long but purely
    # alphabetic identifiers such as table/column names.
    ("long_secret_like", re.compile(r"\b(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{32,}\b")),
)


def redact_text(text: str) -> str:
    """Replace known-sensitive substrings in `text` with `[REDACTED:<label>]`."""
    redacted = text
    for label, pattern in _PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: _redact_value(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def redact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Recursively apply `redact_text` to every string value in `evidence`,
    including strings nested inside lists and dicts."""
    return {key: _redact_value(value) for key, value in evidence.items()}
