"""
Chatbot knowledge base (FAQ) from Supabase.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

KB_FIELDS = "id, question, answer, category, approval_status, created_at"


def list_knowledge(
    *,
    approval_status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = get_supabase().table("chatbot_knowledge").select(KB_FIELDS)
    if approval_status:
        query = query.eq("approval_status", approval_status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []
