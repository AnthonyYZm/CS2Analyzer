from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY = re.compile(r"(?i)(api[_-]?key|authorization|secret|token|password)")
BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]{8,}")
LIKELY_KEY = re.compile(r"\b(?:sk|key)-[A-Za-z0-9_-]{12,}\b")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def redact_text(value: str) -> str:
    value = BEARER.sub("Bearer [REDACTED]", value)
    return LIKELY_KEY.sub("[REDACTED]", value)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def sanitize_untrusted_text(value: str, max_length: int = 200) -> str:
    return CONTROL.sub("", value).strip()[:max_length]
