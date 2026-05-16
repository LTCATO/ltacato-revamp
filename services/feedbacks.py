"""
Tourist feedback from Supabase.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

FEEDBACK_FIELDS = (
    "id, tourist_spot_id, guest_name, rating, comments, suggestions, "
    "sentiment, source, created_at, "
    "tourist_spots(id, name, lgu_id, lgus(id, name))"
)


def list_feedbacks(
    *,
    lgu_id: int | None = None,
    spot_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = get_supabase().table("feedbacks").select(FEEDBACK_FIELDS)
    if spot_id:
        query = query.eq("tourist_spot_id", spot_id)
    response = query.order("created_at", desc=True).limit(limit).execute()
    rows = response.data or []
    if lgu_id:
        filtered = []
        for row in rows:
            spot = row.get("tourist_spots") or {}
            if spot.get("lgu_id") == lgu_id:
                filtered.append(row)
        return filtered
    return rows


def feedback_spot_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    return spot.get("name") or "Unknown spot"


def feedback_lgu_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    lgu = spot.get("lgus") or {}
    return lgu.get("name") or "—"
