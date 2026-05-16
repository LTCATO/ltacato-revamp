"""
Municipality / LGU data from Supabase for public LGU pages.
"""

from __future__ import annotations

from typing import Any

from services.spots import APPROVED_STATUS, SPOT_LIST_FIELDS, get_supabase

MUNICIPALITY_LIST_FIELDS = "id, name, type, zip_code, image, overview"
MUNICIPALITY_DETAIL_FIELDS = (
    "id, name, type, zip_code, image, overview, history, latitude, longitude"
)


def _normalize_type(type_value: str | None) -> str:
    if not type_value:
        return "municipality"
    lowered = type_value.strip().lower()
    if "city" in lowered:
        return "city"
    return "municipality"


def municipality_type_label(type_value: str | None) -> str:
    return "City" if _normalize_type(type_value) == "city" else "Municipality"


def _spot_counts_by_municipality() -> dict[int, int]:
    response = (
        get_supabase()
        .table("tourist_spots")
        .select("municipality_id")
        .eq("status", APPROVED_STATUS)
        .execute()
    )
    counts: dict[int, int] = {}
    for row in response.data or []:
        mid = row.get("municipality_id")
        if mid is not None:
            counts[int(mid)] = counts.get(int(mid), 0) + 1
    return counts


def list_municipalities(
    *,
    type_filter: str | None = None,
    q: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Returns (municipalities enriched with spot_count, summary counts).
    """
    response = (
        get_supabase()
        .table("municipalities")
        .select(MUNICIPALITY_LIST_FIELDS)
        .order("name")
        .execute()
    )
    rows = response.data or []
    spot_counts = _spot_counts_by_municipality()

    municipalities: list[dict[str, Any]] = []
    for row in rows:
        normalized_type = _normalize_type(row.get("type"))
        if type_filter and normalized_type != type_filter:
            continue
        name = row.get("name") or ""
        if q:
            term = q.strip().lower()
            if term and term not in name.lower() and term not in (row.get("overview") or "").lower():
                continue
        municipalities.append(
            {
                **row,
                "type_normalized": normalized_type,
                "type_label": municipality_type_label(row.get("type")),
                "spot_count": spot_counts.get(int(row["id"]), 0),
            }
        )

    summary = {
        "total": len(municipalities),
        "cities": sum(1 for m in municipalities if m["type_normalized"] == "city"),
        "municipalities": sum(1 for m in municipalities if m["type_normalized"] == "municipality"),
        "with_spots": sum(1 for m in municipalities if m["spot_count"] > 0),
    }
    return municipalities, summary


def get_municipality(municipality_id: int) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("municipalities")
            .select(MUNICIPALITY_DETAIL_FIELDS)
            .eq("id", municipality_id)
            .single()
            .execute()
        )
        data = response.data
    except Exception:
        return None

    if not data:
        return None

    data["type_normalized"] = _normalize_type(data.get("type"))
    data["type_label"] = municipality_type_label(data.get("type"))
    return data


def get_municipality_spots(municipality_id: int, limit: int = 24) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("tourist_spots")
        .select(SPOT_LIST_FIELDS)
        .eq("status", APPROVED_STATUS)
        .eq("municipality_id", municipality_id)
        .order("rating", desc=True)
        .order("reviews_count", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_related_municipalities(
    municipality: dict[str, Any], limit: int = 4
) -> list[dict[str, Any]]:
    """Other LGUs of the same type for discovery."""
    type_normalized = municipality.get("type_normalized") or _normalize_type(municipality.get("type"))
    current_id = municipality.get("id")
    all_municipalities, _ = list_municipalities(type_filter=type_normalized)
    return [m for m in all_municipalities if m.get("id") != current_id][:limit]
