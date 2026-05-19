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


def list_event_feedbacks(event_id: int, limit: int = 30) -> list[dict[str, Any]]:
    """Return recent feedbacks for an event, joined with profile names."""
    return (
        get_supabase()
        .table("event_feedbacks")
        .select("*, profiles(first_name, last_name)")
        .eq("event_id", event_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []


def submit_event_feedback(
    tourist_id: str,
    event_id: int,
    rating: int,
    comment: str,
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
