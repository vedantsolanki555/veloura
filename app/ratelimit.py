"""
Tiny in-memory rate limiter (Step 6 Part 4).

Used by /login (5 failed tries / 15 min) and /contact (3 messages / 15 min).
In-memory is fine for one process (local dev / a single gunicorn worker on
Render's free tier). If you ever run several workers, swap this file for
Flask-Limiter + Redis — the call sites would not change.

Never log or store passwords — only timestamps per key.
"""

from collections import defaultdict
from time import monotonic

# key -> list of monotonic() timestamps of recent failures/attempts
_attempts = defaultdict(list)


def _prune(key, window):
    """Drop timestamps older than `window` seconds."""
    now = monotonic()
    _attempts[key] = [t for t in _attempts[key] if now - t < window]


def is_limited(key, max_attempts=5, window=15 * 60):
    """True if this key hit `max_attempts` within the last `window` seconds."""
    _prune(key, window)
    return len(_attempts[key]) >= max_attempts


def record_failure(key, window=15 * 60):
    """Count one failed attempt (or one message sent) against `key`."""
    _prune(key, window)
    _attempts[key].append(monotonic())


def clear_failures(key):
    """Forget everything about `key` (e.g. after a successful login)."""
    _attempts.pop(key, None)
