"""Secret redaction applied before any payload/response is persisted or
reported. This is a Day-1 non-negotiable: captured transcripts routinely
contain real keys the target echoed back.

Redacts common credential shapes and the test canary. Deterministic and
stateless so reports remain diffable.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*\S+"),
     lambda m: f"{m.group(1)}=[REDACTED]"),  # type: ignore[misc]
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"PB_CANARY_SECRET_[A-Za-z0-9]+"), "[REDACTED_CANARY]"),
]


def redact(text: str) -> str:
    """Scrub credential-shaped substrings. Returns input unchanged if clean."""
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


def redact_mapping(data: dict) -> dict:
    """Recursively redact string values in a JSON-ish mapping."""
    return {
        k: (redact(v) if isinstance(v, str) else
            redact_mapping(v) if isinstance(v, dict) else
            [redact(i) if isinstance(i, str) else i for i in v] if isinstance(v, list) else v)
        for k, v in data.items()
    }
