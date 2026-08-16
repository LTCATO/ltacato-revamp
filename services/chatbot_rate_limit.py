"""
Per-user/per-IP rate limiting for LARA chat requests.

The Gemini free tier quota is shared across every visitor to the site — a
single person spamming the chat widget can exhaust it for the whole
province. This is a simple in-memory limiter (same TTLCache pattern used
elsewhere in the chatbot code, no new infra/dependency), scoped per logged-in
user where possible so office-shared IPs don't get penalized together, and
per-IP for anonymous tourists.

Behavior is a cooldown, not a fixed window: each allowed message resets the
TTL, so a key only clears once the caller goes quiet for the full window —
this stops sustained bursts more reliably than a fixed window a spammer
could just wait out and burst again from.
"""

from __future__ import annotations

from typing import Any

from services.ttl_cache import TTLCache

WINDOW_SECONDS = 300  # 5 minutes
MAX_MESSAGES_PER_WINDOW = 20

_counts = TTLCache(max_size=5000, ttl_seconds=WINDOW_SECONDS)


def _rate_limit_key(scope: dict[str, Any], client_ip: str | None) -> str:
    user_id = scope.get("user_id") or scope.get("owner_id")
    if user_id:
        return f"user:{user_id}"
    return f"ip:{client_ip or 'unknown'}"


def check_rate_limit(scope: dict[str, Any], client_ip: str | None) -> bool:
    """Returns True if this request is allowed, False if it should be
    rejected as rate-limited. Counts the request either way once allowed."""
    key = _rate_limit_key(scope, client_ip)
    count = _counts.get(key) or 0
    if count >= MAX_MESSAGES_PER_WINDOW:
        return False
    _counts.set(key, count + 1)
    return True
