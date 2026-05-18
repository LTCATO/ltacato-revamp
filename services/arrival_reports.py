"""
Tourist arrival reports from Supabase.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services.supabase_client import get_supabase

VISITOR_CATEGORIES = ("day_tour", "overnight")

REPORT_FIELDS = (
    "id, tourist_spot_id, lgu_id, submitted_by, report_type, report_date, "
    "visitor_category, overnight_nights, "
    "this_city_male, this_city_female, other_city_male, other_city_female, "
    "other_province_male, other_province_female, foreign_male, foreign_female, "
    "created_at, "
    "tourist_spots(id, name, code), lgus(id, name)"
)

_COUNT_KEYS = (
    "this_city_male",
    "this_city_female",
    "other_city_male",
    "other_city_female",
    "other_province_male",
    "other_province_female",
    "foreign_male",
    "foreign_female",
)


def report_total_visitors(row: dict[str, Any]) -> int:
    if (row.get("visitor_category") or "day_tour") == "overnight":
        return int(row.get("overnight_nights") or 0)
    return sum(int(row.get(k) or 0) for k in _COUNT_KEYS)


def _enrich_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        row["total_visitors"] = report_total_visitors(row)
        row["category_label"] = (
            "Overnight" if row.get("visitor_category") == "overnight" else "Day tour"
        )
    return rows


def list_arrival_reports(
    *,
    lgu_id: int | None = None,
    spot_id: int | None = None,
    owner_id: str | None = None,
    report_type: str | None = None,
    visitor_category: str | None = None,
    require_spot: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = get_supabase().table("arrival_reports").select(REPORT_FIELDS)
    if lgu_id is not None:
        query = query.eq("lgu_id", lgu_id)
    if spot_id is not None:
        query = query.eq("tourist_spot_id", spot_id)
    if report_type:
        query = query.eq("report_type", report_type)
    if visitor_category:
        query = query.eq("visitor_category", visitor_category)
    if require_spot:
        query = query.not_.is_("tourist_spot_id", "null")
    response = query.order("report_date", desc=True).limit(limit).execute()
    rows = response.data or []
    if owner_id:
        spot_ids = _spot_ids_for_owner(owner_id)
        if not spot_ids:
            return []
        rows = [r for r in rows if r.get("tourist_spot_id") in spot_ids]
    return _enrich_rows(rows)


def _spot_ids_for_owner(owner_id: str) -> set[int]:
    from services.spots import list_spots_for_dashboard

    spots = list_spots_for_dashboard(owner_id=owner_id, limit=50)
    return {int(s["id"]) for s in spots if s.get("id") is not None}


def spot_ids_for_lgu(lgu_id: int) -> set[int]:
    from services.spots import list_spots_for_dashboard

    spots = list_spots_for_dashboard(lgu_id=lgu_id, limit=500)
    return {int(s["id"]) for s in spots if s.get("id") is not None}


def create_arrival_report(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "tourist_spot_id",
        "lgu_id",
        "submitted_by",
        "report_type",
        "report_date",
        "visitor_category",
        "overnight_nights",
        *_COUNT_KEYS,
    }
    row = {k: payload[k] for k in allowed if k in payload}
    if row.get("visitor_category") not in VISITOR_CATEGORIES:
        row["visitor_category"] = "day_tour"
    for key in _COUNT_KEYS:
        row[key] = int(row.get(key) or 0)
    row["overnight_nights"] = int(row.get("overnight_nights") or 0)
    response = get_supabase().table("arrival_reports").insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Failed to save arrival report.")
    return _enrich_rows(data)[0]


def arrival_summary_by_lgu(
    report_type: str = "monthly",
    *,
    visitor_category: str | None = None,
) -> list[dict[str, Any]]:
    reports = list_arrival_reports(
        report_type=report_type,
        visitor_category=visitor_category,
        require_spot=True,
        limit=500,
    )
    by_lgu: dict[int, dict[str, Any]] = {}
    for r in reports:
        lid = r.get("lgu_id")
        if lid is None:
            continue
        if lid not in by_lgu:
            lgu = r.get("lgus") or {}
            by_lgu[lid] = {
                "lgu_id": lid,
                "lgu_name": lgu.get("name") if isinstance(lgu, dict) else f"LGU #{lid}",
                "total_visitors": 0,
                "report_count": 0,
            }
        by_lgu[lid]["total_visitors"] += r.get("total_visitors", 0)
        by_lgu[lid]["report_count"] += 1
    return sorted(by_lgu.values(), key=lambda x: x["total_visitors"], reverse=True)


def monthly_spot_reports_for_export(
    *,
    lgu_id: int,
    report_date: date | None = None,
    visitor_category: str | None = None,
) -> list[dict[str, Any]]:
    """Monthly per-spot reports for one LGU (DTA3 / DAE3B export)."""
    query = (
        get_supabase()
        .table("arrival_reports")
        .select(REPORT_FIELDS)
        .eq("lgu_id", lgu_id)
        .eq("report_type", "monthly")
        .not_.is_("tourist_spot_id", "null")
    )
    if report_date is not None:
        query = query.eq("report_date", report_date.isoformat())
    if visitor_category:
        query = query.eq("visitor_category", visitor_category)
    response = query.order("report_date", desc=True).limit(500).execute()
    return _aggregate_by_spot(_enrich_rows(response.data or []))


def _aggregate_by_spot(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per tourist spot (latest month); sum counts if duplicates exist."""
    by_spot: dict[int, dict[str, Any]] = {}
    for r in reports:
        sid = r.get("tourist_spot_id")
        if sid is None:
            continue
        sid = int(sid)
        if sid not in by_spot:
            by_spot[sid] = dict(r)
            continue
        existing = by_spot[sid]
        for key in _COUNT_KEYS:
            existing[key] = int(existing.get(key) or 0) + int(r.get(key) or 0)
        existing["overnight_nights"] = int(existing.get("overnight_nights") or 0) + int(
            r.get("overnight_nights") or 0
        )
        existing["total_visitors"] = report_total_visitors(existing)
    return sorted(
        by_spot.values(),
        key=lambda x: (x.get("tourist_spots") or {}).get("name", ""),
    )


def establishment_reports_for_lgu(lgu_id: int, *, limit: int = 150) -> list[dict[str, Any]]:
    """Daily/weekly reports submitted by establishments under an LGU."""
    response = (
        get_supabase()
        .table("arrival_reports")
        .select(REPORT_FIELDS)
        .eq("lgu_id", lgu_id)
        .in_("report_type", ["daily", "weekly"])
        .not_.is_("tourist_spot_id", "null")
        .order("report_date", desc=True)
        .limit(limit)
        .execute()
    )
    return _enrich_rows(response.data or [])
