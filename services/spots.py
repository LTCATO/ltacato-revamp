from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

SPOT_LIST_FIELDS = (
    "id, name, description, category, main_image_url, rating, reviews_count, "
    "address, hook_title, hook_text, municipality_id, "
    "municipalities(id, name)"
)

SPOT_DETAIL_FIELDS = (
    "*, municipalities(id, name, image, overview)"
)

APPROVED_STATUS = "approved"
PER_PAGE = 12


def _apply_spot_filters(query, *, category: str | None, municipality_id: int | None, q: str | None):
    query = query.eq("status", APPROVED_STATUS)
    if category:
        query = query.eq("category", category.lower())
    if municipality_id:
        query = query.eq("municipality_id", municipality_id)
    if q:
        term = q.strip()
        if term:
            query = query.or_(f"name.ilike.%{term}%,description.ilike.%{term}%,address.ilike.%{term}%")
    return query


def get_municipalities() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("municipalities")
        .select("id, name")
        .order("name")
        .execute()
    )
    return response.data or []


def get_categories() -> list[str]:
    response = (
        get_supabase()
        .table("tourist_spots")
        .select("category")
        .eq("status", APPROVED_STATUS)
        .execute()
    )
    categories = sorted({row["category"] for row in (response.data or []) if row.get("category")})
    return categories


def list_spots(
    *,
    category: str | None = None,
    municipality_id: int | None = None,
    q: str | None = None,
    sort: str = "name",
    page: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    page = max(1, page)
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE - 1

    query = get_supabase().table("tourist_spots").select(SPOT_LIST_FIELDS, count="exact")
    query = _apply_spot_filters(query, category=category, municipality_id=municipality_id, q=q)

    if sort == "rating":
        query = query.order("rating", desc=True).order("reviews_count", desc=True)
    elif sort == "reviews":
        query = query.order("reviews_count", desc=True).order("rating", desc=True)
    else:
        query = query.order("name")

    response = query.range(start, end).execute()
    total = response.count if response.count is not None else len(response.data or [])
    return response.data or [], total


def get_spot(spot_id: int) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("tourist_spots")
            .select(SPOT_DETAIL_FIELDS)
            .eq("id", spot_id)
            .eq("status", APPROVED_STATUS)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def get_spot_feedbacks(spot_id: int, limit: int = 20) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("spot_feedbacks")
        .select("id, guest_name, rating, comments, suggestions, created_at")
        .eq("tourist_spot_id", spot_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_related_spots(spot: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    municipality_id = spot.get("municipality_id")
    category = spot.get("category")
    spot_id = spot.get("id")

    query = (
        get_supabase()
        .table("tourist_spots")
        .select(SPOT_LIST_FIELDS)
        .eq("status", APPROVED_STATUS)
        .neq("id", spot_id)
    )
    if category:
        query = query.eq("category", category)
    elif municipality_id:
        query = query.eq("municipality_id", municipality_id)

    response = query.order("rating", desc=True).limit(limit).execute()
    return response.data or []
