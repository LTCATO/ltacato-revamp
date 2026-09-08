"""
Event engagement (like / bookmark) and feedback (rating + comment).

All write operations are idempotent:
- toggle_event_engagement  → insert if absent, delete if present
- submit_event_feedback    → one-shot insert; returns False if already submitted
"""

from __future__ import annotations

import logging
from typing import Any

from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _adjust_event_counter(event_id: int, col: str, delta: int) -> None:
    """Increment or decrement a numeric column on the events row safely."""
    sb = get_supabase()
    try:
        row = (
            sb.table("events").select(col).eq("id", event_id).single().execute()
        ).data or {}
        current = int(row.get(col) or 0)
        sb.table("events").update({col: max(0, current + delta)}).eq(
            "id", event_id
        ).execute()
    except Exception as exc:
        logger.warning(
            "_adjust_event_counter(%s, %s, %s) failed: %s", event_id, col, delta, exc
        )


# ---------------------------------------------------------------------------
# Engagement (like / bookmark)
# ---------------------------------------------------------------------------


def get_user_event_engagement(tourist_id: str, event_id: int) -> dict[str, bool]:
    """Return {'has_liked': bool, 'has_bookmarked': bool} for the tourist."""
    rows = (
        get_supabase()
        .table("event_engagements")
        .select("type")
        .eq("tourist_id", tourist_id)
        .eq("event_id", event_id)
        .execute()
    ).data or []
    types = {r["type"] for r in rows}
    return {"has_liked": "like" in types, "has_bookmarked": "bookmark" in types}


def toggle_event_engagement(tourist_id: str, event_id: int, eng_type: str) -> bool:
    """Toggle a like or bookmark.

    Returns True if the engagement is now *active*, False if it was removed.
    Raises ValueError if eng_type is not 'like' or 'bookmark'.
    """
    if eng_type not in ("like", "bookmark"):
        raise ValueError(f"Invalid engagement type: {eng_type!r}")

    sb = get_supabase()
    existing = (
        sb.table("event_engagements")
        .select("id")
        .eq("tourist_id", tourist_id)
        .eq("event_id", event_id)
        .eq("type", eng_type)
        .execute()
    ).data or []

    col = "like_count" if eng_type == "like" else "bookmark_count"

    if existing:
        sb.table("event_engagements").delete().eq("id", existing[0]["id"]).execute()
        _adjust_event_counter(event_id, col, -1)
        return False
    else:
        sb.table("event_engagements").insert(
            {
                "tourist_id": tourist_id,
                "event_id": event_id,
                "type": eng_type,
            }
        ).execute()
        _adjust_event_counter(event_id, col, +1)
        return True


# ---------------------------------------------------------------------------
# Feedback (rating + comment)
# ---------------------------------------------------------------------------


def get_event_feedback(tourist_id: str, event_id: int) -> dict[str, Any] | None:
    """Return the existing feedback row for this tourist/event, or None."""
    rows = (
        get_supabase()
        .table("event_feedbacks")
        .select("*")
        .eq("tourist_id", tourist_id)
        .eq("event_id", event_id)
        .execute()
    ).data or []
    return rows[0] if rows else None


def list_event_feedbacks(
    event_id: int, limit: int = 30, *, public_only: bool = False
) -> list[dict[str, Any]]:
    """Return recent feedbacks for an event, joined with profile names.

    public_only excludes hidden reviews — used for the public event page.
    Internal callers (e.g. the rating_avg recompute below) want every row
    regardless of visibility, since hiding a review doesn't change the
    actual rating."""

    def base_query():
        return (
            get_supabase()
            .table("event_feedbacks")
            .select("*, profiles!event_feedbacks_tourist_id_fkey(first_name, last_name)")
            .eq("event_id", event_id)
        )

    if not public_only:
        response = base_query().order("created_at", desc=True).limit(limit).execute()
        return response.data or []

    try:
        response = (
            base_query()
            .eq("is_hidden", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        if "is_hidden" not in str(exc):
            raise
        # sql/event_feedback_hide.sql not migrated yet — show everything
        # rather than erroring the whole event page.
        response = base_query().order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def submit_event_feedback(
    tourist_id: str,
    event_id: int,
    rating: int,
    comment: str,
    images: list[str] | None = None,
) -> bool:
    """Insert a new feedback row.

    Returns False (without raising) if this tourist already submitted feedback
    for this event.  Returns True on success.
    """
    existing = get_event_feedback(tourist_id, event_id)
    if existing:
        return False

    sb = get_supabase()
    sb.table("event_feedbacks").insert(
        {
            "tourist_id": tourist_id,
            "event_id": event_id,
            "rating": max(1, min(5, int(rating))),
            "comment": comment.strip() or None,
            "images": images or [],
            "images_approval_status": "approved",
        }
    ).execute()

    # Recompute running average and review count on the events row
    try:
        all_fb = list_event_feedbacks(event_id, limit=1000)
        rated = [f for f in all_fb if f.get("rating")]
        if rated:
            avg = round(sum(f["rating"] for f in rated) / len(rated), 2)
            sb.table("events").update(
                {
                    "rating_avg": avg,
                    "review_count": len(rated),
                }
            ).eq("id", event_id).execute()
    except Exception as exc:
        logger.warning(
            "Failed to update event rating_avg for event %s: %s", event_id, exc
        )

    return True


def list_event_feedbacks_for_dashboard(
    *, lgu_id: int | None = None, unassigned_only: bool = False, limit: int = 100
) -> list[dict[str, Any]]:
    """Return event feedback rows for the dashboard reviews page, newest first.

    unassigned_only selects feedback only for events with no lgu_id — those
    are run directly by LTCATO province-wide (e.g. Anilag) rather than by a
    specific LGU, so they fall outside every LGU filter and need their own
    bucket instead of silently disappearing."""
    events_join = "events{}(id, title, lgu_id, lgus(id, name))".format(
        "!inner" if (lgu_id or unassigned_only) else ""
    )

    def base_query(fields: str):
        query = get_supabase().table("event_feedbacks").select(fields + ", " + events_join)
        if unassigned_only:
            query = query.is_("events.lgu_id", "null")
        elif lgu_id:
            query = query.eq("events.lgu_id", lgu_id)
        return query.order("created_at", desc=True).limit(limit)

    fields = (
        "id, event_id, rating, comment, images, images_approval_status, is_hidden, "
        "created_at, profiles!event_feedbacks_tourist_id_fkey(first_name, last_name)"
    )
    try:
        response = base_query(fields).execute()
    except Exception as exc:
        if "is_hidden" not in str(exc):
            raise
        # sql/event_feedback_hide.sql not migrated yet.
        response = base_query(fields.replace("is_hidden, ", "")).execute()
        for row in response.data or []:
            row.setdefault("is_hidden", False)
    return response.data or []


def get_event_feedback_for_moderation(feedback_id: int) -> dict[str, Any] | None:
    """Return an event feedback row with its event's lgu_id, for permission checks."""
    rows = (
        get_supabase()
        .table("event_feedbacks")
        .select("id, event_id, events(lgu_id)")
        .eq("id", feedback_id)
        .execute()
    ).data or []
    return rows[0] if rows else None


def set_event_feedback_images_approval(feedback_id: int, status: str) -> None:
    get_supabase().table("event_feedbacks").update(
        {"images_approval_status": status}
    ).eq("id", feedback_id).execute()


def can_manage_event_feedback(user: dict[str, Any], event_lgu_id: int | None) -> bool:
    """Whether user may hide/unhide this event review or moderate its
    photos: an lgu_admin over the event's own LGU, or super_admin/
    ltcato_staff (which also covers LTCATO's own province-wide events,
    where event_lgu_id is None)."""
    role = user.get("role")
    if role in ("super_admin", "ltcato_staff"):
        return True
    if role == "lgu_admin":
        from services.dashboard_auth import resolve_dashboard_lgu_id

        return int(event_lgu_id or -1) == int(resolve_dashboard_lgu_id(user) or -2)
    return False


def set_event_feedback_hidden(feedback_id: int, hidden: bool, *, user: dict[str, Any]) -> None:
    """Hide/unhide an event review from its event's public page without
    deleting it — list_event_feedbacks_for_dashboard() (LGU/LTCATO
    oversight) still sees the row either way."""
    from datetime import datetime, timezone

    row = get_event_feedback_for_moderation(feedback_id)
    if not row:
        raise ValueError("Review not found.")
    event_lgu_id = (row.get("events") or {}).get("lgu_id")
    if not can_manage_event_feedback(user, event_lgu_id):
        raise PermissionError("You can only manage reviews for your own LGU.")
    get_supabase().table("event_feedbacks").update(
        {
            "is_hidden": hidden,
            "hidden_at": datetime.now(timezone.utc).isoformat() if hidden else None,
            "hidden_by": user.get("id") if hidden else None,
        }
    ).eq("id", feedback_id).execute()


def get_user_saved_events(tourist_id: str, limit: int = 24) -> list[dict]:
    """Return events bookmarked by the tourist (for profile page)."""
    rows = (
        get_supabase()
        .table("event_engagements")
        .select(
            "events(id, title, cover_image, start_date, end_date, category, event_status)"
        )
        .eq("tourist_id", tourist_id)
        .eq("type", "bookmark")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    return [r["events"] for r in rows if r.get("events")]
