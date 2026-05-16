"""
Tourist spots from Supabase (updated schema).
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

APPROVED_STATUS = "approved"

SPOT_LIST_FIELDS = (
    "id, name, description, hook_title, hook_text, address, main_image_url, "
    "rating, reviews_count, lgu_id, approval_status, is_featured, "
    "attraction_categories(id, name, code), lgus(id, name)"
)

SPOT_DETAIL_FIELDS = (
    "*, attraction_categories(id, name, code), lgus(id, name, image, overview)"
)

PER_PAGE = 12


def _apply_spot_filters(
    query,
    *,
    category_id: int | None,
    lgu_id: int | None,
    q: str | None,
    approval_status: str | None = APPROVED_STATUS,
):
    if approval_status:
        query = query.eq("approval_status", approval_status)
    if category_id:
        query = query.eq("category_id", category_id)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    if q:
        term = q.strip()
        if term:
            query = query.or_(
                f"name.ilike.%{term}%,description.ilike.%{term}%,address.ilike.%{term}%"
            )
    return query


def get_lgus() -> list[dict[str, Any]]:
    response = get_supabase().table("lgus").select("id, name").order("name").execute()
    return response.data or []


def get_categories() -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("attraction_categories")
        .select("id, code, name")
        .order("name")
        .execute()
    )
    return response.data or []


def list_spots(
    *,
    category_id: int | None = None,
    lgu_id: int | None = None,
    q: str | None = None,
    sort: str = "name",
    page: int = 1,
    approval_status: str | None = APPROVED_STATUS,
) -> tuple[list[dict[str, Any]], int]:
    page = max(1, page)
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE - 1

    query = get_supabase().table("tourist_spots").select(SPOT_LIST_FIELDS, count="exact")
    query = _apply_spot_filters(
        query, category_id=category_id, lgu_id=lgu_id, q=q, approval_status=approval_status
    )

    if sort == "rating":
        query = query.order("rating", desc=True).order("reviews_count", desc=True)
    elif sort == "reviews":
        query = query.order("reviews_count", desc=True).order("rating", desc=True)
    else:
        query = query.order("name")

    response = query.range(start, end).execute()
    total = response.count if response.count is not None else len(response.data or [])
    return response.data or [], total


def list_spots_for_dashboard(
    *,
    lgu_id: int | None = None,
    owner_id: str | None = None,
    approval_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = get_supabase().table("tourist_spots").select(SPOT_LIST_FIELDS)
    if approval_status:
        query = query.eq("approval_status", approval_status)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    if owner_id:
        query = query.eq("owner_id", owner_id)
    response = query.order("updated_at", desc=True).limit(limit).execute()
    return response.data or []


def get_spot(spot_id: int, *, public_only: bool = True) -> dict[str, Any] | None:
    try:
        query = (
            get_supabase()
            .table("tourist_spots")
            .select(SPOT_DETAIL_FIELDS)
            .eq("id", spot_id)
        )
        if public_only:
            query = query.eq("approval_status", APPROVED_STATUS)
        response = query.single().execute()
        return response.data
    except Exception:
        return None


def get_spot_feedbacks(spot_id: int, limit: int = 20) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("feedbacks")
        .select("id, guest_name, rating, comments, suggestions, sentiment, source, created_at")
        .eq("tourist_spot_id", spot_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_related_spots(spot: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    lgu_id = spot.get("lgu_id")
    category = spot.get("attraction_categories")
    category_id = spot.get("category_id")
    spot_id = spot.get("id")

    query = (
        get_supabase()
        .table("tourist_spots")
        .select(SPOT_LIST_FIELDS)
        .eq("approval_status", APPROVED_STATUS)
        .neq("id", spot_id)
    )
    if category_id:
        query = query.eq("category_id", category_id)
    elif lgu_id:
        query = query.eq("lgu_id", lgu_id)

    response = query.order("rating", desc=True).limit(limit).execute()
    return response.data or []


def spot_category_name(spot: dict[str, Any]) -> str:
    cat = spot.get("attraction_categories")
    if isinstance(cat, dict) and cat.get("name"):
        return cat["name"]
    return "Destination"


def spot_lgu_name(spot: dict[str, Any]) -> str:
    lgu = spot.get("lgus")
    if isinstance(lgu, dict) and lgu.get("name"):
        return lgu["name"]
    return "Laguna"
