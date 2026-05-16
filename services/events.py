"""
Events / promotions from Supabase.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

EVENT_FIELDS = (
    "id, title, description, lgu_id, start_date, end_date, venue, banner_image, "
    "approval_status, created_at, lgus(id, name)"
)

APPROVED = "approved"


def list_events(
    *,
    lgu_id: int | None = None,
    approval_status: str | None = None,
    public_approved_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = get_supabase().table("events").select(EVENT_FIELDS)
    if public_approved_only:
        query = query.eq("approval_status", APPROVED)
    elif approval_status:
        query = query.eq("approval_status", approval_status)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    response = query.order("start_date", desc=True).limit(limit).execute()
    return response.data or []


def get_event(event_id: int, *, public_only: bool = False) -> dict[str, Any] | None:
    try:
        query = get_supabase().table("events").select(EVENT_FIELDS).eq("id", event_id)
        if public_only:
            query = query.eq("approval_status", APPROVED)
        response = query.single().execute()
        return response.data
    except Exception:
        return None


def list_events_public(
    *,
    lgu_id: int | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    events = list_events(lgu_id=lgu_id, public_approved_only=True, limit=200)
    if not q:
        return events
    term = q.strip().lower()
    return [
        e
        for e in events
        if term in (e.get("title") or "").lower()
        or term in (e.get("description") or "").lower()
        or term in ((e.get("lgus") or {}).get("name") or "").lower()
        or term in (e.get("venue") or "").lower()
    ]


def get_event_lgu_name(event: dict[str, Any]) -> str:
    lgu = event.get("lgus")
    if isinstance(lgu, dict):
        return lgu.get("name") or "Laguna"
    return "Laguna"


def _parse_event_date(date_str: str | None) -> tuple[str, str]:
    if not date_str:
        return "TBA", "—"
    try:
        parts = str(date_str).split("-")
        if len(parts) >= 3:
            month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month = month_names[int(parts[1])]
            day = str(int(parts[2]))
            return month, day
    except (ValueError, IndexError):
        pass
    return "TBA", "—"


def enrich_event_for_display(event: dict[str, Any]) -> dict[str, Any]:
    month, day = _parse_event_date(event.get("start_date"))
    return {
        **event,
        "image": event.get("banner_image") or "/static/images/kapitolyo.jpg",
        "municipality": get_event_lgu_name(event),
        "summary": event.get("description") or "",
        "date_month": month,
        "date_day": day,
        "time": event.get("venue") or "See details",
        "status": "upcoming",
        "attendee_count": 0,
        "category": "festival",
        "date_label": event.get("start_date") or "Date TBA",
        "date_end_label": event.get("end_date"),
    }


def get_related_events(event: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    lgu_id = event.get("lgu_id")
    events = list_events(lgu_id=lgu_id, public_approved_only=True, limit=limit + 5)
    related = [enrich_event_for_display(e) for e in events if e.get("id") != event.get("id")]
    return related[:limit]
