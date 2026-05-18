"""
Tourist spots from Supabase (updated schema).
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

APPROVED_STATUS = "approved"

SPOT_LIST_FIELDS = (
    "id, name, code, description, hook_title, hook_text, address, main_image_url, "
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


def get_subcategories(*, category_id: int) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("attraction_subcategories")
        .select("id, category_id, code, name")
        .eq("category_id", category_id)
        .order("name")
        .execute()
    )
    return response.data or []


def subcategories_grouped_by_category() -> dict[int, list[dict[str, Any]]]:
    response = (
        get_supabase()
        .table("attraction_subcategories")
        .select("id, category_id, code, name")
        .order("name")
        .execute()
    )
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in response.data or []:
        cid = row.get("category_id")
        if cid is not None:
            grouped.setdefault(int(cid), []).append(row)
    return grouped


def list_claimable_spots_for_lgu(lgu_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
    """Legacy spots in the same LGU with no establishment owner assigned."""
    response = (
        get_supabase()
        .table("tourist_spots")
        .select(SPOT_LIST_FIELDS)
        .eq("lgu_id", lgu_id)
        .is_("owner_id", "null")
        .order("name")
        .limit(limit)
        .execute()
    )
    return response.data or []


def code_belongs_to_category(*, category_id: int, code: int) -> bool:
    return any(s.get("code") == code for s in get_subcategories(category_id=category_id))


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


def owner_has_spot(owner_id: str) -> bool:
    response = (
        get_supabase()
        .table("tourist_spots")
        .select("id", count="exact")
        .eq("owner_id", owner_id)
        .limit(1)
        .execute()
    )
    return bool(response.count and response.count > 0)


def create_tourist_spot_for_owner(
    *,
    owner_id: str,
    lgu_id: int,
    name: str,
    description: str | None = None,
    address: str | None = None,
    opening_hours: str | None = None,
    category_id: int | None = None,
    code: int | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name.strip(),
        "description": (description or "").strip() or None,
        "address": (address or "").strip() or None,
        "opening_hours": (opening_hours or "").strip() or None,
        "lgu_id": lgu_id,
        "owner_id": owner_id,
        "created_by": owner_id,
        "approval_status": "pending_lgu",
    }
    if category_id:
        row["category_id"] = category_id
    if code:
        row["code"] = code
    response = get_supabase().table("tourist_spots").insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Failed to register tourist spot.")
    return data[0]


def claim_tourist_spot_for_owner(
    *,
    spot_id: int,
    owner_id: str,
    lgu_id: int,
) -> dict[str, Any]:
    response = (
        get_supabase()
        .table("tourist_spots")
        .select("id, lgu_id, owner_id, name")
        .eq("id", spot_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise ValueError("Establishment not found.")
    spot = response.data[0]
    if spot.get("owner_id"):
        raise ValueError("This establishment already has an owner.")
    if int(spot.get("lgu_id") or 0) != int(lgu_id):
        raise ValueError("This establishment is not in your LGU.")

    update_res = (
        get_supabase()
        .table("tourist_spots")
        .update({"owner_id": owner_id, "created_by": owner_id})
        .eq("id", spot_id)
        .is_("owner_id", "null")
        .execute()
    )
    if not update_res.data:
        raise RuntimeError("Could not claim establishment. It may have been claimed by someone else.")
    return update_res.data[0]


def update_tourist_spot_for_owner(
    spot_id: int,
    *,
    owner_id: str,
    fields: dict[str, Any],
) -> None:
    allowed = {
        "description",
        "opening_hours",
        "best_time_to_visit",
        "hook_title",
        "hook_text",
        "entrance_fees",
        "what_to_bring",
    }
    payload = {k: fields[k] for k in allowed if k in fields}
    if not payload:
        return
    (
        get_supabase()
        .table("tourist_spots")
        .update(payload)
        .eq("id", spot_id)
        .eq("owner_id", owner_id)
        .execute()
    )


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
