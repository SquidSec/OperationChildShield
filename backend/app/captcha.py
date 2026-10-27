"""Self-hosted proof-of-work captcha.

Why this exists: Cloudflare Turnstile needs keys and an account, and the admin
login fails closed without them. A proof-of-work challenge costs the server
nothing, needs no third party, and is free forever.

How it works
1. The server issues a random challenge, remembers it briefly, and states the
   difficulty in leading zero bits.
2. The browser finds a nonce such that ``sha256(challenge + ":" + nonce)`` has at
   least that many leading zero bits. Expected work is ``2 ** difficulty``
   hashes, which is a fraction of a second for a person and a real CPU cost per
   request for a bot at volume.
3. The server recomputes the hash once, verifies it, and burns the challenge.

Security properties and their limits
- Challenges are single-use and expire, so a solved challenge cannot be replayed.
- A challenge is bound to the client IP, so one solved challenge cannot be
  handed to another host (a soft check: IPs change on mobile networks).
- Verification is one hash, so the server cannot be made to do expensive work.
- Difficulty is server-side and configurable, so cost can be raised without a
  client change.
- A motivated attacker with many cores can still solve these; proof of work
  raises cost, it does not make automation impossible. It is paired with the
  existing per-IP and per-account rate limits.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)

# 17 bits => ~131k hashes expected. Measured ~0.8 s on a desktop browser with the
# synchronous solver in frontend/src/lib/sha256.ts, a few seconds on a phone.
DEFAULT_DIFFICULTY = 17
MIN_DIFFICULTY = 12
MAX_DIFFICULTY = 24

CHALLENGE_TTL_SECONDS = 300
MAX_PENDING_CHALLENGES = 20_000

_lock = threading.Lock()
_pending: dict[str, "_Challenge"] = {}


@dataclass(frozen=True)
class _Challenge:
    ip: str
    difficulty: int
    expires_at: float


def _difficulty() -> int:
    configured = int(getattr(settings, "pow_difficulty", DEFAULT_DIFFICULTY) or DEFAULT_DIFFICULTY)
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, configured))


def _sweep(now: float) -> None:
    """Drop expired challenges. Runs under the lock on issue."""
    expired = [key for key, value in _pending.items() if value.expires_at <= now]
    for key in expired:
        _pending.pop(key, None)


def issue_challenge(*, ip: str = "") -> dict[str, object]:
    """Create a challenge for one client. Returns the public parameters."""
    now = time.time()
    difficulty = _difficulty()
    challenge = secrets.token_hex(24)

    with _lock:
        if len(_pending) >= MAX_PENDING_CHALLENGES:
            _sweep(now)
        # Still full after sweeping: refuse rather than grow without bound.
        if len(_pending) >= MAX_PENDING_CHALLENGES:
            raise RuntimeError("Too many pending captcha challenges")
        _pending[challenge] = _Challenge(
            ip=(ip or "")[:64],
            difficulty=difficulty,
            expires_at=now + CHALLENGE_TTL_SECONDS,
        )

    return {
        "challenge": challenge,
        "difficulty": difficulty,
        "algorithm": "sha256-prefix-zeros",
        "expiresIn": CHALLENGE_TTL_SECONDS,
        "issuedAt": datetime.now(timezone.utc).isoformat(),
    }


def _leading_zero_bits(digest: bytes) -> int:
    count = 0
    for byte in digest:
        if byte == 0:
            count += 8
            continue
        count += 8 - byte.bit_length()
        break
    return count


def solve(challenge: str, difficulty: int, *, max_iterations: int | None = None) -> dict[str, object] | None:
    """Reference solver, used by tests and as server-side documentation.

    The browser has an equivalent implementation in TypeScript.
    """
    if max_iterations is None:
        max_iterations = 2 ** (difficulty + 8)
    prefix = f"{challenge}:".encode("utf-8")
    for nonce in range(max_iterations):
        digest = hashlib.sha256(prefix + str(nonce).encode("ascii")).digest()
        if _leading_zero_bits(digest) >= difficulty:
            return {"nonce": str(nonce), "hash": digest.hex(), "attempts": nonce + 1}
    return None


def verify_solution(
    challenge: str,
    nonce: str,
    *,
    ip: str = "",
    claimed_hash: str = "",
) -> bool:
    """Check a submitted solution and burn the challenge.

    Fails closed: an unknown, expired, or reused challenge is rejected, and a
    challenge issued to a different IP is rejected.
    """
    value = (challenge or "").strip()
    candidate = (nonce or "").strip()
    if not value or not candidate or len(candidate) > 32 or not candidate.isdigit():
        return False

    now = time.time()
    with _lock:
        record = _pending.get(value)
        if record is None:
            return False
        if record.expires_at <= now:
            _pending.pop(value, None)
            return False
        if record.ip and ip and record.ip != ip[:64]:
            # Do not consume it: a shared NAT or a mobile handover should not
            # force the user to start over, but a mismatch must not pass.
            logger.info("Captcha challenge used from a different address")
            return False
        # Single use, regardless of outcome below.
        _pending.pop(value, None)
        difficulty = record.difficulty

    digest = hashlib.sha256(f"{value}:{candidate}".encode("utf-8")).digest()
    if _leading_zero_bits(digest) < difficulty:
        return False

    # The client also reports its hash; a mismatch means a broken client, not an
    # attacker (the recomputation above is authoritative), so log and accept.
    reported = (claimed_hash or "").strip().lower()
    if reported and reported != digest.hex():
        logger.warning("Captcha client reported a hash that does not match")

    return True


def pending_count() -> int:
    """Number of unexpired challenges, for the admin health panel and tests."""
    now = time.time()
    with _lock:
        return sum(1 for value in _pending.values() if value.expires_at > now)


def reset_for_tests() -> None:
    with _lock:
        _pending.clear()
