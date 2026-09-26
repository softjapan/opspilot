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
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    # Coarse catch-all for API-key-shaped strings (long, no whitespace).
    ("long_secret_like", re.compile(r"\b[A-Za-z0-9_-]{24,}\b")),
)


def redact_text(text: str) -> str:
    """Replace known-sensitive substrings in `text` with `[REDACTED:<label>]`."""
    redacted = text
    for label, pattern in _PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


def redact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Recursively apply `redact_text` to every string value in `evidence`."""
    result: dict[str, Any] = {}
    for key, value in evidence.items():
        if isinstance(value, str):
            result[key] = redact_text(value)
        elif isinstance(value, dict):
            result[key] = redact_evidence(value)
        else:
            result[key] = value
    return result
