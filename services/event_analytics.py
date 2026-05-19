"""
Event promotion analytics for LTCATO head and staff.

Engagement rate formula (per event):
  signals = likes + bookmarks + feedback_count + (avg_rating / 5 * feedback_count)
  engagement_rate = (signals / views * 100) capped at 100, or 0 if no views.
Computed live from event_engagements + event_feedbacks + event_analytics.views.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase


def _compute_engagement_rate(
    views: int,
    likes: int,
    bookmarks: int,
    feedback_count: int,
    avg_rating: float,
) -> float:
    """
    Engagement = (likes + bookmarks + feedbacks + rating_weight) / views * 100.
    rating_weight = (avg_rating / 5) * feedback_count  — rewards high-rated events.
    Result is rounded to 2 dp and capped at 100.
    """
    if views <= 0:
        return 0.0
    rating_weight = (avg_rating / 5.0) * feedback_count if avg_rating else 0.0
    signals = likes + bookmarks + feedback_count + rating_weight
    return round(min(signals / views * 100, 100.0), 2)


def _fetch_event_feedback_stats(event_ids: list[int]) -> dict[int, dict[str, Any]]:
    """
    Query event_feedbacks directly for the given event IDs.
    Returns {event_id: {feedback_count, avg_rating, ratings_list}}.
    This is the authoritative source — not the denormalized events columns.
    """
    if not event_ids:
        return {}
    try:
        rows = (
            get_supabase()
            .table("event_feedbacks")
            .select("event_id, rating")
            .in_("event_id", event_ids)
            .execute()
        ).data or []
    except Exception:
        return {}

    stats: dict[int, dict[str, Any]] = {}
    for row in rows:
        eid = row.get("event_id")
        if eid is None:
            continue
        eid = int(eid)
        if eid not in stats:
            stats[eid] = {"feedback_count": 0, "ratings": []}
        stats[eid]["feedback_count"] += 1
        if row.get("rating"):
            stats[eid]["ratings"].append(int(row["rating"]))

    result: dict[int, dict[str, Any]] = {}
    for eid, s in stats.items():
        ratings = s["ratings"]
        result[eid] = {
            "feedback_count": s["feedback_count"],
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        }
    return result


def _fetch_event_engagement_stats(event_ids: list[int]) -> dict[int, dict[str, int]]:
    """
    Query event_engagements directly for likes and bookmarks per event.
    Returns {event_id: {likes, bookmarks}}.
    """
    if not event_ids:
        return {}
    try:
        rows = (
            get_supabase()
            .table("event_engagements")
            .select("event_id, type")
            .in_("event_id", event_ids)
            .execute()
        ).data or []
    except Exception:
        return {}

    stats: dict[int, dict[str, int]] = {}
    for row in rows:
        eid = row.get("event_id")
        if eid is None:
            continue
        eid = int(eid)
        if eid not in stats:
            stats[eid] = {"likes": 0, "bookmarks": 0}
        t = row.get("type", "")
        if t == "like":
            stats[eid]["likes"] += 1
        elif t == "bookmark":
            stats[eid]["bookmarks"] += 1
    return stats


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
        _refresh_engagement_rate(event_id)
    except Exception:
        pass


def _refresh_engagement_rate(event_id: int) -> None:
    """Recompute and persist engagement_rate for a single event."""
    try:
        client = get_supabase()

        ea = client.table("event_analytics").select("views").eq("event_id", event_id).limit(1).execute()
        views = int((ea.data[0].get("views") or 0)) if ea.data else 0

        eng = _fetch_event_engagement_stats([event_id]).get(event_id, {})
        likes = eng.get("likes", 0)
        bookmarks = eng.get("bookmarks", 0)

        fb = _fetch_event_feedback_stats([event_id]).get(event_id, {})
        feedback_count = fb.get("feedback_count", 0)
        avg_rating = fb.get("avg_rating", 0.0)

        rate = _compute_engagement_rate(views, likes, bookmarks, feedback_count, avg_rating)
        client.table("event_analytics").upsert({
            "event_id": event_id,
            "engagement_rate": rate,
        }).execute()
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
    """
    Aggregate analytics across events for dashboard.
    Feedback and engagement are queried live from event_feedbacks and
    event_engagements — not from the potentially stale events denorm columns.
    Revenue estimate is excluded.
    """
    try:
        client = get_supabase()
        rows = (
            client.table("event_analytics")
            .select("event_id, views, engagement_rate, municipality_reach, top_searches, tourist_origin")
            .order("views", desc=True)
            .limit(limit)
            .execute()
        ).data or []
    except Exception:
        rows = []

    event_ids = [int(r["event_id"]) for r in rows if r.get("event_id") is not None]

    # Fetch event metadata
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

    # Fetch live feedback stats from event_feedbacks (authoritative)
    feedback_stats = _fetch_event_feedback_stats(event_ids)

    # Fetch live engagement stats from event_engagements (authoritative)
    engagement_stats = _fetch_event_engagement_stats(event_ids)

    # Enrich rows and recompute engagement
    for r in rows:
        eid = int(r["event_id"]) if r.get("event_id") is not None else None
        r["events"] = event_meta.get(eid, {}) if eid is not None else {}

        views = int(r.get("views") or 0)
        eng = engagement_stats.get(eid, {}) if eid is not None else {}
        fb = feedback_stats.get(eid, {}) if eid is not None else {}

        likes = eng.get("likes", 0)
        bookmarks = eng.get("bookmarks", 0)
        feedback_count = fb.get("feedback_count", 0)
        avg_rating = fb.get("avg_rating", 0.0)

        r["likes"] = likes
        r["bookmarks"] = bookmarks
        r["feedback_count"] = feedback_count
        r["avg_rating"] = avg_rating
        r["engagement_rate"] = _compute_engagement_rate(views, likes, bookmarks, feedback_count, avg_rating)

    total_views = sum(int(r.get("views") or 0) for r in rows)
    total_feedbacks = sum(r.get("feedback_count", 0) for r in rows)
    rates = [r["engagement_rate"] for r in rows if r["engagement_rate"] > 0]
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
        "total_feedbacks": total_feedbacks,
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
