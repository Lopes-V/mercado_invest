"""Small shared operational-error sanitizer; never use it as a substitute for not logging secrets."""
import re

_PATTERNS = (
    (re.compile(r"(?i)(bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(api[_ -]?key|token|secret|password)\s*[=:]\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}"), "[REDACTED_TELEGRAM_TOKEN]"),
)

def sanitize_sensitive_text(value: object, *, limit: int = 1000) -> str:
    message = str(value)
    for pattern, replacement in _PATTERNS:
        message = pattern.sub(replacement, message)
    return message[:limit] or "erro sem mensagem"
