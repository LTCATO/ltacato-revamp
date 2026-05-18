"""
Event promotion analytics for LTCATO head and staff.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase


def record_event_view(event_id: int) -> None:
    try:
        client = get_supabase()
        row = (
            client.table("event_analytics")
            .select("views")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        if row.data:
            views = int(row.data[0].get("views") or 0) + 1
            client.table("event_analytics").update({"views": views}).eq("event_id", event_id).execute()
        else:
            client.table("event_analytics").insert({"event_id": event_id, "views": 1}).execute()
    except Exception:
        pass


def get_event_analytics(event_id: int) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("event_analytics")
            .select("*")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception:
        return None


def get_provincial_event_analytics(*, limit: int = 12) -> dict[str, Any]:
    """Aggregate analytics across events for dashboard."""
    try:
        client = get_supabase()
        rows = (
            client.table("event_analytics")
            .select("*")
            .order("views", desc=True)
            .limit(limit)
            .execute()
        ).data or []
    except Exception:
        rows = []

    event_ids = [int(r["event_id"]) for r in rows if r.get("event_id") is not None]
    event_meta: dict[int, dict[str, Any]] = {}
    if event_ids:
        try:
            ev = (
                get_supabase()
                .table("events")
                .select("id, title, slug, event_status, visibility")
                .in_("id", event_ids)
                .execute()
            )
            for e in ev.data or []:
                if e.get("id") is not None:
                    event_meta[int(e["id"])] = e
        except Exception:
            pass

    for r in rows:
        eid = r.get("event_id")
        r["events"] = event_meta.get(int(eid), {}) if eid is not None else {}

    total_views = sum(int(r.get("views") or 0) for r in rows)
    total_visitors = sum(int(r.get("visitors") or 0) for r in rows)
    total_attendance = sum(int(r.get("attendance") or 0) for r in rows)
    revenue = sum(float(r.get("revenue_estimate") or 0) for r in rows)
    rates = [float(r.get("engagement_rate") or 0) for r in rows if r.get("engagement_rate")]
    avg_engagement = round(sum(rates) / len(rates), 2) if rates else 0.0

    municipality_reach: dict[str, int] = {}
    top_searches: dict[str, int] = {}
    tourist_origin: dict[str, int] = {}

    for row in rows:
        for item in row.get("municipality_reach") or []:
            if isinstance(item, dict):
                name = item.get("name") or item.get("municipality") or "Unknown"
                municipality_reach[name] = municipality_reach.get(name, 0) + int(item.get("count") or 0)
        for term in row.get("top_searches") or []:
            if isinstance(term, dict):
                q = term.get("query") or term.get("term") or ""
            else:
                q = str(term)
            if q:
                top_searches[q] = top_searches.get(q, 0) + 1
        for origin in row.get("tourist_origin") or []:
            if isinstance(origin, dict):
                label = origin.get("origin") or origin.get("name") or "Unknown"
                tourist_origin[label] = tourist_origin.get(label, 0) + int(origin.get("count") or 0)

    return {
        "total_views": total_views,
        "total_visitors": total_visitors,
        "total_attendance": total_attendance,
        "revenue_estimate": round(revenue, 2),
        "avg_engagement_rate": avg_engagement,
        "top_events": rows[:8],
        "municipality_reach": sorted(
            [{"name": k, "count": v} for k, v in municipality_reach.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10],
        "top_searches": sorted(
            [{"query": k, "count": v} for k, v in top_searches.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10],
        "tourist_origin": sorted(
            [{"origin": k, "count": v} for k, v in tourist_origin.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10],
    }
