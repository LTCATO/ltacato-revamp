"""
Tourist arrival reports from Supabase.

Status lifecycle (establishment_owner):
  draft     → record saved locally, not yet visible to LGU
  submitted → owner compiled & submitted the record to the LGU Tourism Office

LGU admins see only submitted records when compiling monthly totals for LTCATO.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services.supabase_client import get_supabase

VISITOR_CATEGORIES = ("day_tour", "overnight")
REPORT_STATUSES = ("draft", "submitted")

REPORT_FIELDS = (
    "id, tourist_spot_id, lgu_id, submitted_by, report_type, report_date, "
    "visitor_category, overnight_nights, status, "
    "this_city_male, this_city_female, other_city_male, other_city_female, "
    "other_province_male, other_province_female, foreign_male, foreign_female, "
    "created_at, "
    "tourist_spots(id, name, code), lgus(id, name)"
)

# Fallback field list used when the status column doesn't exist yet
REPORT_FIELDS_NO_STATUS = (
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
    status: str | None = None,
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
    if status:
        query = query.eq("status", status)
    if require_spot:
        query = query.not_.is_("tourist_spot_id", "null")
    try:
        response = query.order("report_date", desc=True).limit(limit).execute()
    except Exception as exc:
        # status column may not exist yet — fall back to query without it
        if "status" in str(exc):
            query2 = get_supabase().table("arrival_reports").select(REPORT_FIELDS_NO_STATUS)
            if lgu_id is not None:
                query2 = query2.eq("lgu_id", lgu_id)
            if spot_id is not None:
                query2 = query2.eq("tourist_spot_id", spot_id)
            if report_type:
                query2 = query2.eq("report_type", report_type)
            if visitor_category:
                query2 = query2.eq("visitor_category", visitor_category)
            if require_spot:
                query2 = query2.not_.is_("tourist_spot_id", "null")
            response = query2.order("report_date", desc=True).limit(limit).execute()
        else:
            raise
    rows = response.data or []
    if owner_id:
        spot_ids = _spot_ids_for_owner(owner_id)
        if not spot_ids:
            return []
        rows = [r for r in rows if r.get("tourist_spot_id") in spot_ids]
    # If status column doesn't exist yet, treat all rows as submitted
    for row in rows:
        if "status" not in row:
            row["status"] = "submitted"
    # Filter by status in Python if we fell back to the no-status query
    if status:
        rows = [r for r in rows if r.get("status") == status]
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
        "status",
        *_COUNT_KEYS,
    }
    row = {k: payload[k] for k in allowed if k in payload}
    if row.get("visitor_category") not in VISITOR_CATEGORIES:
        row["visitor_category"] = "day_tour"
    if row.get("status") not in REPORT_STATUSES:
        row["status"] = "draft"
    for key in _COUNT_KEYS:
        row[key] = int(row.get(key) or 0)
    row["overnight_nights"] = int(row.get("overnight_nights") or 0)
    try:
        response = get_supabase().table("arrival_reports").insert(row).execute()
    except Exception as exc:
        if "status" in str(exc):
            # Column doesn't exist yet — insert without it
            row.pop("status", None)
            response = get_supabase().table("arrival_reports").insert(row).execute()
        else:
            raise
    data = response.data or []
    if not data:
        raise RuntimeError("Failed to save arrival report.")
    result = _enrich_rows(data)[0]
    if "status" not in result:
        result["status"] = "submitted"
    return result


def delete_arrival_report(report_id: int, *, owner_id: str) -> None:
    """Delete a draft record — only the owner who created it may delete it."""
    try:
        response = (
            get_supabase()
            .table("arrival_reports")
            .select("id, submitted_by, status")
            .eq("id", report_id)
            .execute()
        )
    except Exception as exc:
        if "status" in str(exc):
            response = (
                get_supabase()
                .table("arrival_reports")
                .select("id, submitted_by")
                .eq("id", report_id)
                .execute()
            )
        else:
            raise
    rows = response.data or []
    if not rows:
        raise ValueError("Record not found.")
    row = rows[0]
    if str(row.get("submitted_by")) != str(owner_id):
        raise PermissionError("You can only delete your own records.")
    # If status column doesn't exist, allow deletion (treat as draft)
    if row.get("status", "draft") != "draft":
        raise ValueError("Only draft records can be deleted.")
    get_supabase().table("arrival_reports").delete().eq("id", report_id).execute()


def submit_draft_records(
    *,
    owner_id: str,
    spot_id: int,
    visitor_category: str,
    report_type: str,
    compile_date: str,
) -> int:
    """
    Mark all draft records for a given spot/category/date as submitted,
    and stamp them with the chosen report_type (daily or weekly).
    Returns the number of records updated.
    """
    try:
        response = (
            get_supabase()
            .table("arrival_reports")
            .select("id, submitted_by, status")
            .eq("submitted_by", owner_id)
            .eq("tourist_spot_id", spot_id)
            .eq("visitor_category", visitor_category)
            .eq("report_date", compile_date)
            .eq("status", "draft")
            .execute()
        )
        rows = response.data or []
        ids = [r["id"] for r in rows if str(r.get("submitted_by")) == str(owner_id)]
        if not ids:
            return 0
        get_supabase().table("arrival_reports").update(
            {"status": "submitted", "report_type": report_type}
        ).in_("id", ids).execute()
        return len(ids)
    except Exception as exc:
        if "status" in str(exc):
            return 0
        raise


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
    """Submitted daily/weekly reports from establishments under an LGU."""
    def _build(fields: str):
        return (
            get_supabase()
            .table("arrival_reports")
            .select(fields)
            .eq("lgu_id", lgu_id)
            .in_("report_type", ["daily", "weekly"])
            .not_.is_("tourist_spot_id", "null")
            .order("report_date", desc=True)
            .limit(limit)
        )
    try:
        response = _build(REPORT_FIELDS).eq("status", "submitted").execute()
    except Exception as exc:
        if "status" in str(exc):
            response = _build(REPORT_FIELDS_NO_STATUS).execute()
        else:
            raise
    return _enrich_rows(response.data or [])


def consolidate_establishment_reports(
    lgu_id: int,
    *,
    year: int,
    month: int,
    visitor_category: str,
) -> list[dict[str, Any]]:
    """
    Aggregate submitted daily/weekly establishment reports for a given LGU,
    year, month, and visitor category into one consolidated row per tourist spot.

    Spots that already have a monthly report submitted to LTCATO for this
    year/month/category are excluded — they have already been compiled.
    """
    from calendar import monthrange

    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    def _build(fields: str):
        return (
            get_supabase()
            .table("arrival_reports")
            .select(fields)
            .eq("lgu_id", lgu_id)
            .in_("report_type", ["daily", "weekly"])
            .eq("visitor_category", visitor_category)
            .not_.is_("tourist_spot_id", "null")
            .gte("report_date", first_day.isoformat())
            .lte("report_date", last_day.isoformat())
        )
    try:
        response = _build(REPORT_FIELDS).eq("status", "submitted").execute()
    except Exception as exc:
        if "status" in str(exc):
            response = _build(REPORT_FIELDS_NO_STATUS).execute()
        else:
            raise
    rows = _enrich_rows(response.data or [])

    # Find spots that already have a monthly report for this period/category
    # so we can exclude them from the consolidation view
    try:
        monthly_resp = (
            get_supabase()
            .table("arrival_reports")
            .select("tourist_spot_id")
            .eq("lgu_id", lgu_id)
            .eq("report_type", "monthly")
            .eq("visitor_category", visitor_category)
            .not_.is_("tourist_spot_id", "null")
            .gte("report_date", first_day.isoformat())
            .lte("report_date", last_day.isoformat())
            .execute()
        )
        already_submitted_spot_ids: set[int] = {
            int(r["tourist_spot_id"])
            for r in (monthly_resp.data or [])
            if r.get("tourist_spot_id") is not None
        }
    except Exception:
        already_submitted_spot_ids = set()

    by_spot: dict[int, dict[str, Any]] = {}
    for r in rows:
        sid = r.get("tourist_spot_id")
        if sid is None:
            continue
        sid = int(sid)
        # Skip spots already compiled and submitted to LTCATO this month
        if sid in already_submitted_spot_ids:
            continue
        if sid not in by_spot:
            spot = r.get("tourist_spots") or {}
            by_spot[sid] = {
                "tourist_spot_id": sid,
                "spot_name": spot.get("name", f"Spot #{sid}") if isinstance(spot, dict) else f"Spot #{sid}",
                "spot_code": spot.get("code") if isinstance(spot, dict) else None,
                "lgu_id": lgu_id,
                "visitor_category": visitor_category,
                "report_count": 0,
                "overnight_nights": 0,
                **{k: 0 for k in _COUNT_KEYS},
            }
        entry = by_spot[sid]
        entry["report_count"] += 1
        for k in _COUNT_KEYS:
            entry[k] += int(r.get(k) or 0)
        entry["overnight_nights"] += int(r.get("overnight_nights") or 0)

    for entry in by_spot.values():
        if visitor_category == "overnight":
            entry["total_visitors"] = entry["overnight_nights"]
        else:
            entry["total_visitors"] = sum(entry[k] for k in _COUNT_KEYS)

    return sorted(by_spot.values(), key=lambda x: x["spot_name"])
