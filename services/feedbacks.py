"""
Tourist feedback from Supabase.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase, reset_supabase

FEEDBACK_FIELDS = (
    "id, tourist_spot_id, guest_name, rating, comments, suggestions, "
    "sentiment, source, images, images_approval_status, created_at, "
    "tourist_spots{}(id, name, lgu_id, lgus(id, name))"
)


def list_feedbacks(
    *,
    lgu_id: int | None = None,
    spot_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """The shared Supabase client's connection has been observed to go bad
    for a given query on a long-running process while a brand-new client
    succeeds immediately (Windows/httpx issue) — so a failure gets one retry
    against a freshly-built client before giving up."""
    fields = FEEDBACK_FIELDS.format("!inner" if lgu_id else "")
    for attempt in (1, 2):
        try:
            query = get_supabase().table("feedbacks").select(fields)
            if spot_id:
                query = query.eq("tourist_spot_id", spot_id)
            if lgu_id:
                query = query.eq("tourist_spots.lgu_id", lgu_id)
            response = query.order("created_at", desc=True).limit(limit).execute()
            return response.data or []
        except Exception:
            if attempt == 1:
                reset_supabase()
                continue
            raise
    return []  # unreachable, keeps type-checkers happy


def get_feedback_for_moderation(feedback_id: int) -> dict[str, Any] | None:
    """Return a feedback row with its spot's lgu_id, for permission checks."""
    rows = (
        get_supabase()
        .table("feedbacks")
        .select("id, tourist_spot_id, tourist_spots(lgu_id)")
        .eq("id", feedback_id)
        .execute()
    ).data or []
    return rows[0] if rows else None


def set_feedback_images_approval(feedback_id: int, status: str) -> None:
    get_supabase().table("feedbacks").update(
        {"images_approval_status": status}
    ).eq("id", feedback_id).execute()


def feedback_spot_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    return spot.get("name") or "Unknown spot"


def feedback_lgu_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    lgu = spot.get("lgus") or {}
    return lgu.get("name") or "—"
