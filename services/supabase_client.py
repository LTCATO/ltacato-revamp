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
