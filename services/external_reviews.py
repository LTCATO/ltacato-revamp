"""
External / scraped reviews for decision support.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

REVIEW_FIELDS = (
    "id, tourist_spot_id, source, reviewer_name, review_text, "
    "sentiment, review_date, scraped_at, tourist_spots(id, name, lgus(id, name))"
)


def list_external_reviews(*, limit: int = 100) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("external_reviews")
        .select(REVIEW_FIELDS)
        .order("scraped_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []
