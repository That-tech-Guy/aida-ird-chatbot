"""
Local privacy filters for A.I.D.A.

The goal is to remove common personal/sensitive patterns before text is
sent to Gemini. This is a defensive layer, not a guarantee that every
possible piece of personal information can be detected.
"""

from __future__ import annotations

import re
from typing import Iterable


EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?"
    r"(?:\(?264\)?[\s.-]?)?"
    r"\d{3}[\s.-]\d{4}(?!\w)"
)

CARD_OR_LONG_NUMBER_RE = re.compile(
    r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)"
)

LABELED_ID_RE = re.compile(
    r"\b("
    r"account(?:\s+number)?|"
    r"taxpayer(?:\s+number)?|"
    r"tin|"
    r"registration(?:\s+number)?|"
    r"reference(?:\s+number)?|"
    r"national\s+id|"
    r"passport(?:\s+number)?"
    r")\s*[:#-]?\s*[A-Z0-9-]{4,}",
    re.IGNORECASE,
)

SECURITY_CODE_RE = re.compile(
    r"\b("
    r"otp|"
    r"one[-\s]?time\s+(?:password|code)|"
    r"security\s+code|"
    r"verification\s+code|"
    r"authentication\s+code|"
    r"pin"
    r")\s*[:#-]?\s*\d{3,8}\b",
    re.IGNORECASE,
)

EXPLICIT_NAME_RE = re.compile(
    r"\b(my\s+name\s+is|name\s*[:=-])"
    r"\s+([A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*){0,4})",
    re.IGNORECASE,
)

EXPLICIT_ADDRESS_RE = re.compile(
    r"\b(my\s+address\s+is|address\s*[:=-])"
    r"\s+([^,\n]{5,120})",
    re.IGNORECASE,
)


def redact_private_text(text: str) -> tuple[str, bool]:
    """Redact common private data before model calls or analytics logs."""

    if not isinstance(text, str):
        return "", False

    redacted = text

    substitutions = (
        (EMAIL_RE, "[EMAIL REDACTED]"),
        (PHONE_RE, "[PHONE REDACTED]"),
        (CARD_OR_LONG_NUMBER_RE, "[LONG NUMBER REDACTED]"),
        (
            LABELED_ID_RE,
            lambda match: f"{match.group(1)}: [IDENTIFIER REDACTED]",
        ),
        (
            SECURITY_CODE_RE,
            lambda match: f"{match.group(1)}: [SECURITY CODE REDACTED]",
        ),
        (
            EXPLICIT_NAME_RE,
            lambda match: f"{match.group(1)} [NAME REDACTED]",
        ),
        (
            EXPLICIT_ADDRESS_RE,
            lambda match: f"{match.group(1)} [ADDRESS REDACTED]",
        ),
    )

    for pattern, replacement in substitutions:
        redacted = pattern.sub(replacement, redacted)

    return redacted, redacted != text


def redact_history(
    messages: Iterable[dict[str, str]],
) -> tuple[list[dict[str, str]], bool]:
    clean: list[dict[str, str]] = []
    changed = False

    for message in messages:
        content, content_changed = redact_private_text(
            str(message.get("content", ""))
        )
        clean.append(
            {
                "role": str(message.get("role", "")),
                "content": content,
            }
        )
        changed = changed or content_changed

    return clean, changed
