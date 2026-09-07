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


def list_feedbacks_for_owner(
    owner_id: str, *, spot_id: int | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """Reviews left on the establishment owner's own spot(s), including
    hidden ones (the owner needs to see what they've hidden to undo it)."""
    from services.spots import list_owner_spot_ids

    spot_ids = list_owner_spot_ids(owner_id)
    if spot_id is not None:
        spot_ids = [s for s in spot_ids if int(s) == int(spot_id)]
    if not spot_ids:
        return []

    def base_query(fields: str):
        return (
            get_supabase()
            .table("feedbacks")
            .select(fields)
            .in_("tourist_spot_id", spot_ids)
            .order("created_at", desc=True)
            .limit(limit)
        )

    fields = (
        "id, tourist_spot_id, guest_name, rating, comments, suggestions, "
        "sentiment, images, images_approval_status, is_hidden, created_at, "
        "tourist_spots(id, name)"
    )
    try:
        response = base_query(fields).execute()
    except Exception as exc:
        if "is_hidden" not in str(exc):
            raise
        # sql/feedback_hide.sql not migrated yet — show reviews as all-public
        # rather than erroring the whole page.
        fallback_fields = fields.replace("is_hidden, ", "")
        response = base_query(fallback_fields).execute()
        for row in response.data or []:
            row.setdefault("is_hidden", False)
    return response.data or []


def _verify_feedback_owner(feedback_id: int, owner_id: str) -> dict[str, Any]:
    rows = (
        get_supabase()
        .table("feedbacks")
        .select("id, tourist_spot_id, tourist_spots(owner_id)")
        .eq("id", feedback_id)
        .execute()
    ).data or []
    if not rows:
        raise ValueError("Review not found.")
    row = rows[0]
    spot = row.get("tourist_spots") or {}
    if str(spot.get("owner_id")) != str(owner_id):
        raise PermissionError("You can only manage reviews for your own establishment.")
    return row


def set_feedback_hidden(feedback_id: int, hidden: bool, *, owner_id: str) -> None:
    """Let an establishment owner hide a bad review from their spot's public
    page without deleting it — LGU/LTCATO oversight (list_feedbacks) still
    sees it either way."""
    from datetime import datetime, timezone

    _verify_feedback_owner(feedback_id, owner_id)
    get_supabase().table("feedbacks").update(
        {
            "is_hidden": hidden,
            "hidden_at": datetime.now(timezone.utc).isoformat() if hidden else None,
            "hidden_by": owner_id if hidden else None,
        }
    ).eq("id", feedback_id).execute()


def feedback_spot_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    return spot.get("name") or "Unknown spot"


def feedback_lgu_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    lgu = spot.get("lgus") or {}
    return lgu.get("name") or "—"
