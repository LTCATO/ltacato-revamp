"""
Spot engagement (like / bookmark) per tourist.

Feedback for spots lives in the existing ``public.feedbacks`` table
(tourist_spot_id FK).  The unique constraint added by the migration
(feedbacks_tourist_spot_unique) prevents duplicate submissions.
"""

from __future__ import annotations

import logging
from typing import Any

from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engagement (like / bookmark)
# ---------------------------------------------------------------------------


def get_user_spot_engagement(tourist_id: str, spot_id: int) -> dict[str, bool]:
    """Return {'has_liked': bool, 'has_bookmarked': bool} for the tourist."""
    rows = (
        get_supabase()
        .table("spot_engagements")
        .select("type")
        .eq("tourist_id", tourist_id)
        .eq("spot_id", spot_id)
        .execute()
    ).data or []
    types = {r["type"] for r in rows}
    return {"has_liked": "like" in types, "has_bookmarked": "bookmark" in types}


def toggle_spot_engagement(tourist_id: str, spot_id: int, eng_type: str) -> bool:
    """Toggle a like or bookmark for a tourist spot.

    Returns True if the engagement is now *active*, False if it was removed.
    Raises ValueError if eng_type is not 'like' or 'bookmark'.
    """
    if eng_type not in ("like", "bookmark"):
        raise ValueError(f"Invalid engagement type: {eng_type!r}")

    sb = get_supabase()
    existing = (
        sb.table("spot_engagements")
        .select("id")
        .eq("tourist_id", tourist_id)
        .eq("spot_id", spot_id)
        .eq("type", eng_type)
        .execute()
    ).data or []

    if existing:
        sb.table("spot_engagements").delete().eq("id", existing[0]["id"]).execute()
        return False
    else:
        sb.table("spot_engagements").insert(
            {
                "tourist_id": tourist_id,
                "spot_id": spot_id,
                "type": eng_type,
            }
        ).execute()
        return True


# ---------------------------------------------------------------------------
# Feedback (via existing feedbacks table)
# ---------------------------------------------------------------------------


def get_user_spot_feedback(tourist_id: str, spot_id: int) -> dict[str, Any] | None:
    """Return the existing feedback row for this tourist/spot, or None."""
    rows = (
        get_supabase()
        .table("feedbacks")
        .select("*")
        .eq("tourist_id", tourist_id)
        .eq("tourist_spot_id", spot_id)
        .execute()
    ).data or []
    return rows[0] if rows else None


def get_spot_engagement_counts(spot_id: int) -> dict[str, int]:
    """Count total likes and bookmarks for a spot from the spot_engagements table."""
    rows = (
        get_supabase()
        .table("spot_engagements")
        .select("type")
        .eq("spot_id", spot_id)
        .execute()
    ).data or []
    like_count = sum(1 for r in rows if r.get("type") == "like")
    bookmark_count = sum(1 for r in rows if r.get("type") == "bookmark")
    return {"like_count": like_count, "bookmark_count": bookmark_count}


def get_user_saved_spots(tourist_id: str, limit: int = 24) -> list[dict]:
    """Return spots bookmarked by the tourist (for profile page)."""
    rows = (
        get_supabase()
        .table("spot_engagements")
        .select("tourist_spots(id, name, main_image_url, address, lgu_id, lgus(name))")
        .eq("tourist_id", tourist_id)
        .eq("type", "bookmark")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []
    return [r["tourist_spots"] for r in rows if r.get("tourist_spots")]
