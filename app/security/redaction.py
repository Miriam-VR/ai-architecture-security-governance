"""Secret/PII redaction applied to logs and audit details (V08/V13)."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+"), "[REDACTED_DB_URL]"),
    (re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[=:]\s*[^\s,;\"']+"), r"\1=[REDACTED]"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
]
_SENSITIVE_KEYS = re.compile(r"(?i)^(.*[_-])?(password|passwd|secret|api[_-]?key|token|authorization|database_url)$")


def redact_text(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def redact(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: "[REDACTED]" if _SENSITIVE_KEYS.search(str(k)) else redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    return obj
