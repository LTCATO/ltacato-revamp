"""
Chatbot knowledge base (FAQ) from Supabase.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

KB_FIELDS = "id, question, answer, category, approval_status, created_at, created_by, approved_by"


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


def get_knowledge_entry(entry_id: int) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("chatbot_knowledge")
            .select(KB_FIELDS)
            .eq("id", entry_id)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def create_knowledge(
    *,
    question: str,
    answer: str,
    category: str = "",
    created_by: str,
    auto_approve: bool = False,
) -> tuple[bool, str | None]:
    question = (question or "").strip()
    answer = (answer or "").strip()
    category = (category or "").strip()

    if not question:
        return False, "Question is required."
    if not answer:
        return False, "Answer is required."

    payload: dict[str, Any] = {
        "question": question,
        "answer": answer,
        "category": category or None,
        "created_by": created_by,
        "approval_status": "approved" if auto_approve else "pending",
    }
    if auto_approve:
        payload["approved_by"] = created_by

    try:
        get_supabase().table("chatbot_knowledge").insert(payload).execute()
        return True, None
    except Exception as exc:
        return False, f"Could not save FAQ entry: {exc}"


def update_knowledge(
    entry_id: int,
    *,
    question: str,
    answer: str,
    category: str = "",
    approved_by: str | None = None,
) -> tuple[bool, str | None]:
    question = (question or "").strip()
    answer = (answer or "").strip()
    category = (category or "").strip()

    if not question:
        return False, "Question is required."
    if not answer:
        return False, "Answer is required."

    payload: dict[str, Any] = {
        "question": question,
        "answer": answer,
        "category": category or None,
        # Keep approved if an approver is provided, otherwise reset to pending
        "approval_status": "approved" if approved_by else "pending",
    }
    if approved_by:
        payload["approved_by"] = approved_by

    try:
        get_supabase().table("chatbot_knowledge").update(payload).eq("id", entry_id).execute()
        return True, None
    except Exception as exc:
        return False, f"Could not update FAQ entry: {exc}"


def delete_knowledge(entry_id: int) -> tuple[bool, str | None]:
    try:
        get_supabase().table("chatbot_knowledge").delete().eq("id", entry_id).execute()
        return True, None
    except Exception as exc:
        return False, f"Could not delete FAQ entry: {exc}"
