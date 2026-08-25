import os

# pyrefly: ignore [missing-import]
from supabase import Client, create_client

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and key must be set in environment")
        _client = create_client(url, key)
    return _client


def reset_supabase() -> None:
    """Drop the cached client so the next get_supabase() call builds a fresh
    one. The client is a single long-lived instance for the life of the
    process; its underlying connection has been observed to intermittently
    go bad for a given query while a brand-new client succeeds immediately —
    call this to recover instead of requiring a full process restart."""
    global _client
    _client = None
