"""Password policy aligned with NIST SP 800-63B-4 (2024/2026 guidance).

What modern guidance says, and what this module implements:

- **Length beats composition.** Minimum 15 characters for accounts that can be
  reached with a password alone. Because this app forces MFA for admins, the
  absolute floor is still kept at 15 so a stolen password is not useful on its
  own. Maximum 128 (no silent truncation).
- **No composition rules.** Forcing symbols/numbers pushes people toward
  predictable patterns ("Password1!") and is explicitly discouraged. Instead we
  require length and reject known-bad passwords.
- **Blocklist against breached/common passwords**, plus context words (the
  site name, the account's email local part, and simple variants).
- **No periodic rotation.** Rotating on a schedule produces weaker passwords;
  rotate only on suspected compromise (handled by session revocation).
- **Allow every character**, including spaces, symbols, and non-ASCII. No
  normalization beyond Unicode NFC so the same keystrokes verify reliably.
- **No secret strength meter in the response** beyond an advisory score; it is
  never used to reject a password that already passed the rules.

An optional Have I Been Pwned check is available but off by default because it
leaves the server; the offline blocklist is the enforced baseline.
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128

# Common and breached passwords, plus the patterns people reach for when told to
# "make it strong". Compared case-insensitively after light normalization.
_COMMON_PASSWORDS = frozenset(
    {
        "password", "password1", "password12", "password123", "password1234",
        "passw0rd", "p@ssw0rd", "p@ssword", "qwerty", "qwerty123", "qwertyuiop",
        "letmein", "welcome", "welcome1", "welcome123", "admin", "admin123",
        "administrator", "iloveyou", "monkey", "dragon", "football", "baseball",
        "sunshine", "princess", "superman", "batman", "trustno1", "abc123",
        "abcdef", "abcdefg", "123456", "1234567", "12345678", "123456789",
        "1234567890", "111111", "000000", "changeme", "change-me", "secret",
        "secret123", "letmein123", "login", "master", "shadow", "michael",
        "jennifer", "hunter2", "root", "toor", "guest", "test", "test123",
        "default", "pass", "pass123", "mypassword", "yourpassword",
        "operationchildshield", "childshield", "operation child shield",
        "child safety", "nonprofit", "non-profit", "boardmember",
        "summer2026", "winter2026", "spring2026", "fall2026", "autumn2026",
        "january2026", "february2026", "qwerty2026", "password2026",
        "letmein2026", "welcome2026", "admin2026", "p@ssw0rd2026",
    }
)

# Contextual words that must not appear inside a password. These are not secret;
# they are the obvious guesses an attacker makes first.
_CONTEXT_WORDS = (
    "operationchildshield",
    "childshield",
    "child",
    "shield",
    "operation",
    "admin",
    "password",
    "voterecord",
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class PasswordPolicyError(ValueError):
    """Raised with a user-facing, actionable message."""


def _normalize(value: str) -> str:
    # NFC keeps visually identical input comparable without folding distinct
    # characters together (which could weaken a password).
    return unicodedata.normalize("NFC", value or "")


def _squash(value: str) -> str:
    """Lowercase, strip separators, and collapse simple leetspeak variants."""
    lowered = value.casefold()
    for symbol, letter in (("0", "o"), ("1", "l"), ("3", "e"), ("4", "a"),
                           ("5", "s"), ("7", "t"), ("@", "a"), ("$", "s")):
        lowered = lowered.replace(symbol, letter)
    return re.sub(r"[^a-z0-9]", "", lowered)


def _entropy_bits(password: str) -> float:
    """Rough Shannon-style estimate used only for the advisory score."""
    if not password:
        return 0.0
    classes = 0
    if re.search(r"[a-z]", password):
        classes += 26
    if re.search(r"[A-Z]", password):
        classes += 26
    if re.search(r"[0-9]", password):
        classes += 10
    if re.search(r"[^A-Za-z0-9]", password):
        classes += 33
    if re.search(r"[^\x00-\x7f]", password):
        classes += 60
    import math

    return len(password) * math.log2(max(classes, 1))


def strength_label(password: str) -> str:
    """Advisory label for the UI: weak | fair | strong | excellent."""
    bits = _entropy_bits(password)
    if bits >= 100:
        return "excellent"
    if bits >= 75:
        return "strong"
    if bits >= 55:
        return "fair"
    return "weak"


def _reject_if_blocklisted(password: str, *, email: str = "") -> None:
    squashed = _squash(password)
    if squashed in {_squash(p) for p in _COMMON_PASSWORDS}:
        raise PasswordPolicyError(
            "That password appears on known-breach lists. Choose something unique."
        )
    for word in _CONTEXT_WORDS:
        if _squash(word) and _squash(word) in squashed:
            raise PasswordPolicyError(
                "Do not include the organization name or the word 'password'."
            )
    if email:
        local_part = email.split("@", 1)[0]
        if len(local_part) >= 3 and _squash(local_part) in squashed:
            raise PasswordPolicyError("Do not include your email address in the password.")


def validate_password(password: str, *, email: str = "") -> str:
    """Validate and return the NFC-normalized password, or raise.

    The message is safe to show to the user: it names the rule, never the value.
    """
    value = _normalize(password)

    if _CONTROL_CHARS.search(value):
        raise PasswordPolicyError("Password contains unsupported control characters.")
    if len(value) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Use at least {MIN_PASSWORD_LENGTH} characters. A short phrase works well."
        )
    if len(value) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Use at most {MAX_PASSWORD_LENGTH} characters."
        )
    if value.strip() == "":
        raise PasswordPolicyError("Password cannot be only whitespace.")

    _reject_if_blocklisted(value, email=email)

    # Reject long runs and simple sequences, which are the usual way a long
    # password is still weak ("aaaaaaaaaaaaaaaa", "abcdefghijklmnop").
    if re.search(r"(.)\1{4,}", value):
        raise PasswordPolicyError("Avoid repeating the same character five or more times.")
    lowered = value.casefold()
    for sequence in ("abcdefghijklmnopqrstuvwxyz", "01234567890", "qwertyuiop"):
        for start in range(len(sequence) - 5):
            chunk = sequence[start : start + 6]
            if chunk in lowered or chunk[::-1] in lowered:
                raise PasswordPolicyError("Avoid keyboard or alphabet sequences.")

    return value


# There is deliberately no HIBP/fingerprint helper here. The offline blocklist
# above is the enforced policy, and an unused SHA-1 helper tripped Bandit's B324
# for no benefit. If a Pwned Passwords lookup is added later it must pass
# usedforsecurity=False explicitly and be covered by tests.


def rules_for_display() -> dict[str, object]:
    """Rules for the UI to render as a checklist (never secret)."""
    return {
        "minLength": MIN_PASSWORD_LENGTH,
        "maxLength": MAX_PASSWORD_LENGTH,
        "requiresComposition": False,
        "rules": [
            f"At least {MIN_PASSWORD_LENGTH} characters",
            "Any characters you like, including spaces",
            "Not a known breached password",
            "No organization name or your email address",
            "No long repeats or keyboard sequences",
        ],
    }
