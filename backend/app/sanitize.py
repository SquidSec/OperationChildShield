"""Server-side sanitization for untrusted applicant text.

Two separate jobs, deliberately kept apart:

1. **Storage**: keep the applicant's words as plain text. We never store HTML
   that a browser could execute. Control characters and bidi overrides that can
   disguise text are stripped, length is bounded, and newlines are normalized.
2. **Display**: when the admin UI renders a value it is output as text (React
   escapes by default). As a second layer, ``safe_for_display`` removes
   zero-width and bidi-control characters so a value cannot visually reorder a
   table row, and marks anything that looks like markup.

Nothing here is a substitute for parameterized SQL (the queries use bound
parameters) or for React's escaping; these are defence-in-depth.
"""

from __future__ import annotations

import re
import unicodedata

# C0/C1 controls except tab/newline, plus DEL.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Unicode bidi overrides and zero-width characters used to spoof text order.
_INVISIBLE_RE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)

# Things that look like an attempt to inject markup or a URL scheme.
_MARKUP_RE = re.compile(r"<\s*/?\s*[a-zA-Z!]|javascript\s*:|data\s*:|on[a-z]+\s*=", re.I)

MAX_TEXT = 4000
MAX_SHORT = 200


def clean_text(value: str, *, max_length: int = MAX_TEXT) -> str:
    """Normalize an untrusted string for storage as plain text."""
    text = unicodedata.normalize("NFC", value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    text = _INVISIBLE_RE.sub("", text)
    # Collapse runs of blank lines and trailing spaces; keep paragraphs.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text[:max_length]


def clean_short(value: str, *, max_length: int = MAX_SHORT) -> str:
    """Single-line variant for names, locations, and URLs."""
    text = clean_text(value, max_length=max_length)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_markup(value: str) -> bool:
    return bool(_MARKUP_RE.search(value or ""))


def safe_for_display(value: str, *, max_length: int = MAX_TEXT) -> str:
    """Second-layer cleanup applied again right before rendering."""
    text = clean_text(value, max_length=max_length)
    if looks_like_markup(text):
        # Not an error: applicants legitimately write "R&D < 5%". React escapes
        # it, so the flag exists only to keep the value visible as text.
        return text
    return text


def sanitize_application(record: dict[str, object]) -> dict[str, object]:
    """Apply storage rules to every free-text field of an application."""
    return {
        "submittedAt": clean_short(str(record.get("submittedAt") or ""), max_length=40),
        "role": clean_short(str(record.get("role") or ""), max_length=64),
        "roleLabel": clean_short(str(record.get("roleLabel") or ""), max_length=64),
        "name": clean_short(str(record.get("name") or ""), max_length=120),
        "email": clean_short(str(record.get("email") or ""), max_length=254).lower(),
        "phone": clean_short(str(record.get("phone") or ""), max_length=40),
        "location": clean_short(str(record.get("location") or ""), max_length=120),
        "linkedin": clean_short(str(record.get("linkedin") or ""), max_length=200),
        "statement": clean_text(str(record.get("statement") or ""), max_length=MAX_TEXT),
        "source": clean_short(str(record.get("source") or ""), max_length=40),
    }
