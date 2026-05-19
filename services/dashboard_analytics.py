"""
Dashboard analytics aggregates (Supabase-backed with safe fallbacks).
Role-scoped: super_admin, ltcato_staff, lgu_admin, establishment_owner.
"""

from __future__ import annotations

from typing import Any

from services.arrival_reports import arrival_summary_by_lgu, list_arrival_reports
from services.event_analytics import get_provincial_event_analytics
from services.feedbacks import list_feedbacks
from services.lgus import list_lgus_simple
from services.spots import APPROVED_STATUS, list_spots, list_spots_for_dashboard
from services.supabase_client import get_supabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_table(table: str, **filters) -> int:
    try:
        query = get_supabase().table(table).select("id", count="exact")
        for key, val in filters.items():
            query = query.eq(key, val)
        response = query.limit(1).execute()
        return response.count or 0
    except Exception:
        return 0


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Visitor breakdown helpers
# ---------------------------------------------------------------------------

def _visitor_breakdown(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate visitor counts by origin category across a list of reports."""
    totals = {
        "this_city": 0,
        "other_city": 0,
        "other_province": 0,
        "foreign": 0,
        "overnight_nights": 0,
        "day_tour": 0,
        "overnight": 0,
    }
    for r in reports:
        cat = r.get("visitor_category", "day_tour")
        if cat == "overnight":
            totals["overnight"] += r.get("total_visitors", 0)
            totals["overnight_nights"] += int(r.get("overnight_nights") or 0)
        else:
            totals["day_tour"] += r.get("total_visitors", 0)
        totals["this_city"] += int(r.get("this_city_male") or 0) + int(r.get("this_city_female") or 0)
        totals["other_city"] += int(r.get("other_city_male") or 0) + int(r.get("other_city_female") or 0)
        totals["other_province"] += int(r.get("other_province_male") or 0) + int(r.get("other_province_female") or 0)
        totals["foreign"] += int(r.get("foreign_male") or 0) + int(r.get("foreign_female") or 0)
    return totals


def _gender_breakdown(reports: list[dict[str, Any]]) -> dict[str, int]:
    male = 0
    female = 0
    for r in reports:
        for key in ("this_city_male", "other_city_male", "other_province_male", "foreign_male"):
            male += int(r.get(key) or 0)
        for key in ("this_city_female", "other_city_female", "other_province_female", "foreign_female"):
            female += int(r.get(key) or 0)
    return {"male": male, "female": female}


def _monthly_trend(reports: list[dict[str, Any]], *, months: int = 6) -> list[dict[str, Any]]:
    """Build a monthly visitor trend from a list of reports (any type)."""
    from collections import defaultdict
    by_month: dict[str, int] = defaultdict(int)
    for r in reports:
        date_str = str(r.get("report_date") or "")
        if len(date_str) >= 7:
            month_key = date_str[:7]  # YYYY-MM
            by_month[month_key] += r.get("total_visitors", 0)
    sorted_months = sorted(by_month.keys(), reverse=True)[:months]
    sorted_months.reverse()
    return [{"month": m, "visitors": by_month[m]} for m in sorted_months]


def _spot_visitor_ranking(reports: list[dict[str, Any]], *, top: int = 8) -> list[dict[str, Any]]:
    """Rank tourist spots by total visitors from a list of reports."""
    from collections import defaultdict
    by_spot: dict[int, dict[str, Any]] = {}
    for r in reports:
        sid = r.get("tourist_spot_id")
        if sid is None:
            continue
        sid = int(sid)
        if sid not in by_spot:
            spot = r.get("tourist_spots") or {}
            by_spot[sid] = {
                "spot_id": sid,
                "spot_name": spot.get("name") or f"Spot #{sid}",
                "spot_code": spot.get("code"),
                "total_visitors": 0,
                "report_count": 0,
            }
        by_spot[sid]["total_visitors"] += r.get("total_visitors", 0)
        by_spot[sid]["report_count"] += 1
    return sorted(by_spot.values(), key=lambda x: x["total_visitors"], reverse=True)[:top]


def _feedback_stats(feedbacks: list[dict[str, Any]]) -> dict[str, Any]:
    ratings = [f["rating"] for f in feedbacks if f.get("rating")]
    avg = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    sentiments = [f.get("sentiment", "neutral") for f in feedbacks]
    pos = sum(1 for s in sentiments if s == "positive")
    neg = sum(1 for s in sentiments if s == "negative")
    neu = len(sentiments) - pos - neg
    total = len(sentiments) or 1
    return {
        "count": len(feedbacks),
        "avg_rating": avg,
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "positive_pct": round(pos / total * 100),
        "negative_pct": round(neg / total * 100),
        "neutral_pct": round(neu / total * 100),
    }


def _top_rated_spots(lgu_id: int | None = None, *, limit: int = 5) -> list[dict[str, Any]]:
    try:
        query = (
            get_supabase()
            .table("tourist_spots")
            .select("id, name, rating, reviews_count, lgu_id, lgus(name)")
            .eq("approval_status", "approved")
            .gt("reviews_count", 0)
            .order("rating", desc=True)
            .order("reviews_count", desc=True)
        )
        if lgu_id:
            query = query.eq("lgu_id", lgu_id)
        return query.limit(limit).execute().data or []
    except Exception:
        return []


def _recent_feedbacks(lgu_id: int | None = None, *, limit: int = 5) -> list[dict[str, Any]]:
    try:
        query = (
            get_supabase()
            .table("feedbacks")
            .select("id, guest_name, rating, comments, sentiment, created_at, tourist_spots(name, lgus(name))")
            .order("created_at", desc=True)
        )
        rows = query.limit(limit * 3).execute().data or []
        if lgu_id:
            rows = [
                r for r in rows
                if (r.get("tourist_spots") or {}).get("lgu_id") == lgu_id
                or (r.get("tourist_spots") or {}).get("lgus", {}) is not None
            ]
        return rows[:limit]
    except Exception:
        return []


def _spot_approval_breakdown(lgu_id: int | None = None) -> dict[str, int]:
    statuses = ["pending_lgu", "pending_ltcato", "approved", "rejected"]
    result = {}
    for s in statuses:
        try:
            q = get_supabase().table("tourist_spots").select("id", count="exact").eq("approval_status", s)
            if lgu_id:
                q = q.eq("lgu_id", lgu_id)
            result[s] = q.limit(1).execute().count or 0
        except Exception:
            result[s] = 0
    return result


def _event_status_breakdown(lgu_id: int | None = None) -> dict[str, int]:
    statuses = ["draft", "upcoming", "ongoing", "finished"]
    result = {}
    for s in statuses:
        try:
            q = get_supabase().table("events").select("id", count="exact").eq("event_status", s)
            if lgu_id:
                q = q.eq("lgu_id", lgu_id)
            result[s] = q.limit(1).execute().count or 0
        except Exception:
            result[s] = 0
    return result


def _itinerary_stats() -> dict[str, Any]:
    try:
        total = get_supabase().table("itineraries").select("id", count="exact").limit(1).execute().count or 0
        purposes = {}
        for p in ("vacation", "business", "educational", "family", "adventure"):
            try:
                c = get_supabase().table("itineraries").select("id", count="exact").eq("trip_purpose", p).limit(1).execute().count or 0
                purposes[p] = c
            except Exception:
                purposes[p] = 0
        return {"total": total, "by_purpose": purposes}
    except Exception:
        return {"total": 0, "by_purpose": {}}


def _passport_stats() -> dict[str, Any]:
    try:
        total = get_supabase().table("tourist_passports").select("id", count="exact").limit(1).execute().count or 0
        stamps = get_supabase().table("passport_stamps").select("id", count="exact").limit(1).execute().count or 0
        return {"total_passports": total, "total_stamps": stamps}
    except Exception:
        return {"total_passports": 0, "total_stamps": 0}


def _engagement_stats() -> dict[str, Any]:
    try:
        spot_likes = get_supabase().table("spot_engagements").select("id", count="exact").eq("type", "like").limit(1).execute().count or 0
        spot_bookmarks = get_supabase().table("spot_engagements").select("id", count="exact").eq("type", "bookmark").limit(1).execute().count or 0
        event_likes = get_supabase().table("event_engagements").select("id", count="exact").eq("type", "like").limit(1).execute().count or 0
        event_bookmarks = get_supabase().table("event_engagements").select("id", count="exact").eq("type", "bookmark").limit(1).execute().count or 0
        return {
            "spot_likes": spot_likes,
            "spot_bookmarks": spot_bookmarks,
            "event_likes": event_likes,
            "event_bookmarks": event_bookmarks,
        }
    except Exception:
        return {"spot_likes": 0, "spot_bookmarks": 0, "event_likes": 0, "event_bookmarks": 0}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_analytics_overview(*, lgu_id: int | None = None) -> dict[str, Any]:
    """Province-wide or LGU-scoped analytics for super_admin / ltcato_staff / lgu_admin."""
    try:
        _, spot_total = list_spots(lgu_id=lgu_id, page=1, approval_status=APPROVED_STATUS)
    except Exception:
        spot_total = 0

    # Pending queues
    pending_lgu = _count_table("tourist_spots", approval_status="pending_lgu")
    pending_ltcato = _count_table("tourist_spots", approval_status="pending_ltcato")
    pending_events = _count_table("events", approval_status="pending")
    pending_chatbot = _count_table("chatbot_knowledge", approval_status="pending")

    # Spot approval breakdown
    spot_approval = _spot_approval_breakdown(lgu_id)

    # Event status breakdown
    event_status = _event_status_breakdown(lgu_id)

    # Arrivals
    all_monthly = list_arrival_reports(lgu_id=lgu_id, report_type="monthly", limit=500)
    monthly_total = sum(r.get("total_visitors", 0) for r in all_monthly)
    visitor_breakdown = _visitor_breakdown(all_monthly)
    gender_breakdown = _gender_breakdown(all_monthly)
    monthly_trend = _monthly_trend(all_monthly, months=6)
    spot_ranking = _spot_visitor_ranking(all_monthly, top=8)
    arrival_by_lgu = arrival_summary_by_lgu("monthly")[:10]

    # Feedbacks
    feedbacks = list_feedbacks(lgu_id=lgu_id, limit=200)
    feedback_stats = _feedback_stats(feedbacks)
    top_rated = _top_rated_spots(lgu_id, limit=5)
    recent_fb = _recent_feedbacks(lgu_id, limit=5)

    # Event promo analytics (province-wide only)
    event_promo_analytics: dict[str, Any] | None = None
    if lgu_id is None:
        try:
            event_promo_analytics = get_provincial_event_analytics(limit=12)
        except Exception:
            event_promo_analytics = None

    # Engagement
    engagement = _engagement_stats() if lgu_id is None else {}

    # Itineraries & passports (province-wide only)
    itinerary_stats = _itinerary_stats() if lgu_id is None else {}
    passport_stats = _passport_stats() if lgu_id is None else {}

    # LGU count
    lgu_count = len(list_lgus_simple())

    return {
        # Summary KPIs
        "spot_total": spot_total,
        "pending_lgu_spots": pending_lgu,
        "pending_ltcato_spots": pending_ltcato,
        "pending_events": pending_events,
        "pending_chatbot": pending_chatbot,
        "monthly_arrival_total": monthly_total,
        "feedback_count": feedback_stats["count"],
        "avg_feedback_rating": feedback_stats["avg_rating"],
        "lgu_count": lgu_count,
        # Breakdowns
        "spot_approval": spot_approval,
        "event_status": event_status,
        "visitor_breakdown": visitor_breakdown,
        "gender_breakdown": gender_breakdown,
        "monthly_trend": monthly_trend,
        "spot_ranking": spot_ranking,
        "arrival_by_lgu": arrival_by_lgu,
        "feedback_stats": feedback_stats,
        "top_rated_spots": top_rated,
        "recent_feedbacks": recent_fb,
        # Province-wide extras
        "event_promo_analytics": event_promo_analytics,
        "engagement": engagement,
        "itinerary_stats": itinerary_stats,
        "passport_stats": passport_stats,
    }


def get_establishment_analytics(*, owner_id: str | None = None) -> dict[str, Any]:
    """Detailed analytics for establishment owner dashboard."""
    all_reports: list[dict[str, Any]] = []
    spot: dict[str, Any] | None = None
    spot_id: int | None = None

    if owner_id:
        spots = list_spots_for_dashboard(owner_id=owner_id, limit=5)
        if spots:
            spot = spots[0]
            spot_id = int(spot["id"])
        all_reports = list_arrival_reports(owner_id=owner_id, limit=200)

    daily = [r for r in all_reports if r.get("report_type") == "daily"]
    weekly = [r for r in all_reports if r.get("report_type") == "weekly"]
    all_submitted = daily + weekly

    total_visitors = sum(r.get("total_visitors", 0) for r in all_submitted)
    visitor_breakdown = _visitor_breakdown(all_submitted)
    gender_breakdown = _gender_breakdown(all_submitted)
    monthly_trend = _monthly_trend(all_submitted, months=6)

    # Feedbacks for this spot
    feedbacks: list[dict[str, Any]] = []
    if spot_id:
        try:
            fb_res = (
                get_supabase()
                .table("feedbacks")
                .select("id, guest_name, rating, comments, sentiment, created_at")
                .eq("tourist_spot_id", spot_id)
                .order("created_at", desc=True)
                .limit(100)
                .execute()
            )
            feedbacks = fb_res.data or []
        except Exception:
            feedbacks = []

    feedback_stats = _feedback_stats(feedbacks)

    # Engagements for this spot
    spot_likes = 0
    spot_bookmarks = 0
    if spot_id:
        try:
            spot_likes = get_supabase().table("spot_engagements").select("id", count="exact").eq("spot_id", spot_id).eq("type", "like").limit(1).execute().count or 0
            spot_bookmarks = get_supabase().table("spot_engagements").select("id", count="exact").eq("spot_id", spot_id).eq("type", "bookmark").limit(1).execute().count or 0
        except Exception:
            pass

    # Passport stamps for this spot
    stamp_count = 0
    if spot_id:
        try:
            stamp_count = get_supabase().table("passport_stamps").select("id", count="exact").eq("tourist_spot_id", spot_id).limit(1).execute().count or 0
        except Exception:
            pass

    return {
        # Summary KPIs
        "visitors_this_month": total_visitors,
        "reports_submitted": len(all_submitted),
        "daily_reports": len(daily),
        "weekly_reports": len(weekly),
        "avg_rating": feedback_stats["avg_rating"],
        "pending_reports": max(0, 1 - len(weekly)),
        # Breakdowns
        "visitor_breakdown": visitor_breakdown,
        "gender_breakdown": gender_breakdown,
        "monthly_trend": monthly_trend,
        "feedback_stats": feedback_stats,
        "recent_feedbacks": feedbacks[:5],
        # Engagement
        "spot_likes": spot_likes,
        "spot_bookmarks": spot_bookmarks,
        "stamp_count": stamp_count,
        # Spot info
        "spot": spot,
    }
