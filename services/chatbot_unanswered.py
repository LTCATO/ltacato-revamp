"""
Logged LARA chat misses (route/spot/event/faq questions it couldn't answer),
for LTCATO staff to review and promote into chatbot_knowledge FAQ entries.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from services.chatbot_knowledge import create_knowledge
from services.supabase_client import get_supabase

FIELDS = (
    "id, query_text, normalized_text, intent, role, miss_count, "
    "first_seen_at, last_seen_at, resolved, promoted_knowledge_id"
)


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip("?!. ")
    return text


def log_unanswered_query(
    query_text: str, *, intent: str | None = None, role: str | None = None
) -> None:
    """Best-effort — must never raise. Dedupes on normalized_text, bumping
    miss_count/last_seen_at instead of inserting a duplicate row."""
    query_text = (query_text or "").strip()
    normalized = _normalize(query_text)
    if not normalized:
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        existing = (
            get_supabase()
            .table("chatbot_unanswered_queries")
            .select("id, miss_count")
            .eq("normalized_text", normalized)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            row = existing[0]
            get_supabase().table("chatbot_unanswered_queries").update(
                {"miss_count": (row.get("miss_count") or 0) + 1, "last_seen_at": now}
            ).eq("id", row["id"]).execute()
        else:
            get_supabase().table("chatbot_unanswered_queries").insert(
                {
                    "query_text": query_text,
                    "normalized_text": normalized,
                    "intent": intent,
                    "role": role,
                    "miss_count": 1,
                    "first_seen_at": now,
                    "last_seen_at": now,
                }
            ).execute()
    except Exception as exc:
        print(f"[chatbot_unanswered] log_unanswered_query failed (swallowed): {exc}")


def list_unanswered_queries(
    *, resolved: bool = False, limit: int = 100
) -> list[dict[str, Any]]:
    query = (
        get_supabase()
        .table("chatbot_unanswered_queries")
        .select(FIELDS)
        .eq("resolved", resolved)
    )
    response = (
        query.order("miss_count", desc=True)
        .order("last_seen_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def promote_to_knowledge(
    entry_id: int, *, answer: str, category: str, created_by: str
) -> tuple[bool, str | None]:
    try:
        row = (
            get_supabase()
            .table("chatbot_unanswered_queries")
            .select("id, query_text")
            .eq("id", entry_id)
            .single()
            .execute()
            .data
        )
    except Exception:
        row = None
    if not row:
        return False, "Logged question not found."

    ok, err = create_knowledge(
        question=row["query_text"],
        answer=answer,
        category=category,
        created_by=created_by,
        auto_approve=True,
    )
    if not ok:
        return False, err

    try:
        new_entry = (
            get_supabase()
            .table("chatbot_knowledge")
            .select("id")
            .eq("question", row["query_text"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        promoted_id = new_entry[0]["id"] if new_entry else None
        get_supabase().table("chatbot_unanswered_queries").update(
            {"resolved": True, "promoted_knowledge_id": promoted_id}
        ).eq("id", entry_id).execute()
    except Exception as exc:
        # The FAQ entry was created successfully — losing the resolved flag
        # is cosmetic, so don't report this as a failure to the caller.
        print(f"[chatbot_unanswered] promote resolved-flag update failed: {exc}")

    return True, None


def dismiss_unanswered_query(entry_id: int) -> tuple[bool, str | None]:
    try:
        get_supabase().table("chatbot_unanswered_queries").update(
            {"resolved": True}
        ).eq("id", entry_id).execute()
        return True, None
    except Exception as exc:
        return False, f"Could not dismiss logged question: {exc}"
