"""
Tourist arrival reports from Supabase.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

REPORT_FIELDS = (
    "id, tourist_spot_id, lgu_id, report_type, report_date, "
    "this_city_male, this_city_female, other_city_male, other_city_female, "
    "other_province_male, other_province_female, foreign_male, foreign_female, "
    "created_at, "
    "tourist_spots(id, name), lgus(id, name)"
)


def report_total_visitors(row: dict[str, Any]) -> int:
    keys = (
        "this_city_male",
        "this_city_female",
        "other_city_male",
        "other_city_female",
        "other_province_male",
        "other_province_female",
        "foreign_male",
        "foreign_female",
    )
    return sum(int(row.get(k) or 0) for k in keys)


def list_arrival_reports(
    *,
    lgu_id: int | None = None,
    spot_id: int | None = None,
    report_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = get_supabase().table("arrival_reports").select(REPORT_FIELDS)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    if spot_id:
        query = query.eq("tourist_spot_id", spot_id)
    if report_type:
        query = query.eq("report_type", report_type)
    response = query.order("report_date", desc=True).limit(limit).execute()
    rows = response.data or []
    for row in rows:
        row["total_visitors"] = report_total_visitors(row)
    return rows


def arrival_summary_by_lgu(report_type: str = "monthly") -> list[dict[str, Any]]:
    reports = list_arrival_reports(report_type=report_type, limit=500)
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
