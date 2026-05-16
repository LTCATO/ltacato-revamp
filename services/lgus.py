"""
LGU (local government unit) data from Supabase `lgus` table.
"""

from __future__ import annotations

from typing import Any

from services.spots import APPROVED_STATUS, SPOT_LIST_FIELDS
from services.supabase_client import get_supabase

LGU_LIST_FIELDS = "id, name, type, zip_code, image, overview"
LGU_DETAIL_FIELDS = "id, name, type, zip_code, image, overview, history, latitude, longitude"


def _normalize_type(type_value: str | None) -> str:
    if not type_value:
        return "municipality"
    lowered = type_value.strip().lower()
    return "city" if "city" in lowered else "municipality"


def lgu_type_label(type_value: str | None) -> str:
    return "City" if _normalize_type(type_value) == "city" else "Municipality"


def _spot_counts_by_lgu() -> dict[int, int]:
    response = (
        get_supabase()
        .table("tourist_spots")
        .select("lgu_id")
        .eq("approval_status", APPROVED_STATUS)
        .execute()
    )
    counts: dict[int, int] = {}
    for row in response.data or []:
        lid = row.get("lgu_id")
        if lid is not None:
            counts[int(lid)] = counts.get(int(lid), 0) + 1
    return counts


def list_lgus(*, type_filter: str | None = None, q: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    response = (
        get_supabase()
        .table("lgus")
        .select(LGU_LIST_FIELDS)
        .order("name")
        .execute()
    )
    rows = response.data or []
    spot_counts = _spot_counts_by_lgu()

    lgus: list[dict[str, Any]] = []
    for row in rows:
        normalized_type = _normalize_type(row.get("type"))
        if type_filter and normalized_type != type_filter:
            continue
        name = row.get("name") or ""
        if q:
            term = q.strip().lower()
            if term and term not in name.lower() and term not in (row.get("overview") or "").lower():
                continue
        lgus.append(
            {
                **row,
                "type_normalized": normalized_type,
                "type_label": lgu_type_label(row.get("type")),
                "spot_count": spot_counts.get(int(row["id"]), 0),
            }
        )

    summary = {
        "total": len(lgus),
        "cities": sum(1 for m in lgus if m["type_normalized"] == "city"),
        "municipalities": sum(1 for m in lgus if m["type_normalized"] == "municipality"),
        "with_spots": sum(1 for m in lgus if m["spot_count"] > 0),
    }
    return lgus, summary


def get_lgu(lgu_id: int) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("lgus")
            .select(LGU_DETAIL_FIELDS)
            .eq("id", lgu_id)
            .single()
            .execute()
        )
        data = response.data
    except Exception:
        return None
    if not data:
        return None
    data["type_normalized"] = _normalize_type(data.get("type"))
    data["type_label"] = lgu_type_label(data.get("type"))
    return data


def get_lgu_spots(lgu_id: int, limit: int = 24, *, approved_only: bool = True) -> list[dict[str, Any]]:
    query = (
        get_supabase()
        .table("tourist_spots")
        .select(SPOT_LIST_FIELDS)
        .eq("lgu_id", lgu_id)
    )
    if approved_only:
        query = query.eq("approval_status", APPROVED_STATUS)
    response = query.order("rating", desc=True).limit(limit).execute()
    return response.data or []


def get_related_lgus(lgu: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
    type_normalized = lgu.get("type_normalized") or _normalize_type(lgu.get("type"))
    current_id = lgu.get("id")
    all_lgus, _ = list_lgus(type_filter=type_normalized)
    return [m for m in all_lgus if m.get("id") != current_id][:limit]


def list_lgus_simple() -> list[dict[str, Any]]:
    response = get_supabase().table("lgus").select("id, name, type").order("name").execute()
    return response.data or []
