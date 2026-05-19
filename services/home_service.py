"""
Home page data service.
Fetches real events and trending spots from Supabase for the public home page.
"""

from __future__ import annotations

from typing import Any

from services.events import list_home_events
from services.supabase_client import get_supabase


def get_home_events(limit: int = 3) -> list[dict[str, Any]]:
    """Upcoming/ongoing public events for the home page event section."""
    try:
        return list_home_events(limit=limit)
    except Exception:
        return []


def get_trending_spots(limit: int = 3) -> list[dict[str, Any]]:
    """
    Fetch trending tourist spots based on a composite score:
    - Internal feedback avg rating + count (from feedbacks table)
    - Online review positive sentiment count (from external_reviews table)
    - Spot's own rating + reviews_count fields
    - Featured flag

    Returns top spots with name, image, description, LGU, category, and score.
    """
    try:
        # Get all approved spots with basic info
        spots = (
            get_supabase()
            .table("tourist_spots")
            .select(
                "id, name, description, hook_text, hook_title, "
                "main_image_url, rating, reviews_count, is_featured, "
                "lgus(id, name), attraction_categories(id, name)"
            )
            .eq("approval_status", "approved")
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception:
        return []

    if not spots:
        return []

    # Get internal feedback counts and avg ratings per spot
    fb_scores: dict[int, dict] = {}
    try:
        fb_rows = (
            get_supabase()
            .table("feedbacks")
            .select("tourist_spot_id, rating, sentiment")
            .execute()
            .data
            or []
        )
        for row in fb_rows:
            sid = row.get("tourist_spot_id")
            if not sid:
                continue
            if sid not in fb_scores:
                fb_scores[sid] = {"ratings": [], "positive": 0, "count": 0}
            fb_scores[sid]["count"] += 1
            r = row.get("rating") or 0
            if r:
                fb_scores[sid]["ratings"].append(r)
            if row.get("sentiment") == "positive":
                fb_scores[sid]["positive"] += 1
    except Exception:
        pass

    # Get online review positive counts per spot
    ext_scores: dict[int, int] = {}
    try:
        ext_rows = (
            get_supabase()
            .table("external_reviews")
            .select("tourist_spot_id, sentiment")
            .execute()
            .data
            or []
        )
        for row in ext_rows:
            sid = row.get("tourist_spot_id")
            if sid and row.get("sentiment") == "positive":
                ext_scores[sid] = ext_scores.get(sid, 0) + 1
    except Exception:
        pass

    # Calculate trending score per spot
    scored: list[dict] = []
    for spot in spots:
        sid = spot["id"]
        fb = fb_scores.get(sid, {})

        # Base: spot's own stored rating (0–5)
        base_rating = float(spot.get("rating") or 0)

        # Internal feedback avg rating bonus
        fb_ratings = fb.get("ratings", [])
        fb_avg = sum(fb_ratings) / len(fb_ratings) if fb_ratings else 0
        fb_count = fb.get("count", 0)
        fb_positive = fb.get("positive", 0)

        # Online review positive count bonus
        ext_positive = ext_scores.get(sid, 0)

        # Composite score:
        # base_rating (0-5) + fb_avg boost + engagement volume + featured bonus
        score = (
            base_rating * 10  # stored rating weight
            + fb_avg * 8  # internal feedback avg
            + min(fb_count, 20) * 0.5  # engagement count (capped)
            + fb_positive * 1.5  # internal positive sentiment
            + ext_positive * 2.0  # online positive reviews
            + (15 if spot.get("is_featured") else 0)  # featured bonus
        )

        scored.append({**spot, "_score": score})

    # Sort by score descending, return top N
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:limit]
