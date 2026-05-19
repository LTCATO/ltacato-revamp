"""
Decision Support Service — aggregates all data sources for the dashboard.
Results are cached for 10 minutes to keep page load under 3 seconds.

Scoping:
  - super_admin / ltcato_staff : province-wide (lgu_id=None, owner_id=None)
  - lgu_admin                  : filtered to their LGU (lgu_id=<int>)
  - establishment_owner        : filtered to their spot (owner_id=<uuid str>)
"""

from __future__ import annotations

import time as _time
from typing import Any

from services.scrapers.insights_generator import (
    get_event_insights,
    get_spot_insights,
)
from services.scrapers.news_scraper import get_latest_news
from services.scrapers.reviews_scraper import (
    get_event_feedbacks_for_display,
    get_online_reviews_for_display,
    get_spot_feedbacks_for_display,
)
from services.scrapers.sentiment_analyzer import (
    get_event_feedback_sentiment as get_event_sentiment_summary,
)
from services.scrapers.sentiment_analyzer import (
    get_external_review_sentiment_summary,
    get_feedback_sentiment_summary,
)
from services.scrapers.trends_scraper import get_latest_trends
from services.scrapers.weather_scraper import get_latest_weather, get_weather_alert
from services.supabase_client import get_supabase

# ── Module-level cache (10-minute TTL) ────────────────────────────────────
_CACHE: dict[str, Any] = {"data": None, "ts": 0.0}
_CACHE_TTL = 600  # 10 minutes


# ── Scoped data helpers ───────────────────────────────────────────────────


def _filter_insights_by_lgu(insights: list[dict], lgu_name: str) -> list[dict]:
    """Keep only insights whose lgu_name matches (case-insensitive)."""
    if not lgu_name:
        return insights
    lgu_lower = lgu_name.lower()
    return [i for i in insights if (i.get("lgu_name") or "").lower() == lgu_lower]


def _filter_insights_by_spot_ids(insights: list[dict], spot_ids: set) -> list[dict]:
    """Keep only insights whose spot_id is in the given set."""
    if not spot_ids:
        return insights
    return [i for i in insights if i.get("spot_id") in spot_ids]


def _get_lgu_name(lgu_id: int) -> str:
    try:
        rows = (
            get_supabase()
            .table("lgus")
            .select("name")
            .eq("id", lgu_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0]["name"] if rows else ""
    except Exception:
        return ""


def _get_owner_spot_ids(owner_id: str) -> set:
    """Return the set of tourist_spot ids owned by this user."""
    try:
        rows = (
            get_supabase()
            .table("tourist_spots")
            .select("id")
            .eq("owner_id", owner_id)
            .execute()
            .data
            or []
        )
        return {r["id"] for r in rows}
    except Exception:
        return set()


def _get_event_sentiment_for_lgu(lgu_id: int) -> dict[str, Any]:
    """Event feedback sentiment scoped to a single LGU."""
    try:
        rows = (
            get_supabase()
            .table("event_feedbacks")
            .select("comment, rating, events(lgu_id)")
            .execute()
            .data
            or []
        )
        rows = [r for r in rows if (r.get("events") or {}).get("lgu_id") == lgu_id]
    except Exception:
        rows = []
    total = len(rows)
    positive = sum(1 for r in rows if (r.get("rating") or 0) >= 4)
    negative = sum(1 for r in rows if (r.get("rating") or 0) <= 2)
    neutral = total - positive - negative
    ratings = [r["rating"] for r in rows if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "positive_pct": round(positive / total * 100, 1) if total else 0,
        "negative_pct": round(negative / total * 100, 1) if total else 0,
        "neutral_pct": round(neutral / total * 100, 1) if total else 0,
        "avg_rating": avg_rating,
    }


def _get_ext_sentiment_for_lgu(lgu_id: int) -> dict[str, Any]:
    """External review sentiment scoped to spots in a single LGU."""
    try:
        rows = (
            get_supabase()
            .table("external_reviews")
            .select("sentiment, tourist_spots(lgu_id)")
            .execute()
            .data
            or []
        )
        rows = [r for r in rows if (r.get("tourist_spots") or {}).get("lgu_id") == lgu_id]
    except Exception:
        rows = []
    total = len(rows)
    positive = sum(1 for r in rows if r.get("sentiment") == "positive")
    negative = sum(1 for r in rows if r.get("sentiment") == "negative")
    neutral = total - positive - negative
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "positive_pct": round(positive / total * 100, 1) if total else 0,
        "negative_pct": round(negative / total * 100, 1) if total else 0,
        "neutral_pct": round(neutral / total * 100, 1) if total else 0,
    }


def _get_feedbacks_for_lgu(lgu_id: int, limit: int = 50) -> list[dict]:
    rows = get_spot_feedbacks_for_display(limit=limit * 3)
    return [
        r for r in rows
        if (r.get("tourist_spots") or {}).get("lgus", {}) and
           (r.get("tourist_spots") or {}).get("lgus", {}).get("id") == lgu_id
           or (r.get("tourist_spots") or {}).get("lgu_id") == lgu_id
    ][:limit]


def _get_event_feedbacks_for_lgu(lgu_id: int, limit: int = 50) -> list[dict]:
    rows = get_event_feedbacks_for_display(limit=limit * 3)
    return [
        r for r in rows
        if (r.get("events") or {}).get("lgu_id") == lgu_id
    ][:limit]


def _get_online_reviews_for_lgu(lgu_id: int, limit: int = 50) -> list[dict]:
    rows = get_online_reviews_for_display(limit=limit * 3)
    return [
        r for r in rows
        if (r.get("tourist_spots") or {}).get("lgu_id") == lgu_id
    ][:limit]


def _get_feedbacks_for_owner(spot_ids: set, limit: int = 50) -> list[dict]:
    rows = get_spot_feedbacks_for_display(limit=limit * 3)
    return [
        r for r in rows
        if (r.get("tourist_spots") or {}).get("id") in spot_ids
    ][:limit]


def _get_online_reviews_for_owner(spot_ids: set, limit: int = 50) -> list[dict]:
    rows = get_online_reviews_for_display(limit=limit * 3)
    return [
        r for r in rows
        if (r.get("tourist_spots") or {}).get("id") in spot_ids
    ][:limit]


def _get_sentiment_for_spot_ids(spot_ids: set) -> dict[str, Any]:
    try:
        rows = (
            get_supabase()
            .table("feedbacks")
            .select("sentiment, rating, tourist_spot_id")
            .execute()
            .data
            or []
        )
        rows = [r for r in rows if r.get("tourist_spot_id") in spot_ids]
    except Exception:
        rows = []
    total = len(rows)
    positive = sum(1 for r in rows if r.get("sentiment") == "positive")
    negative = sum(1 for r in rows if r.get("sentiment") == "negative")
    neutral = total - positive - negative
    ratings = [r["rating"] for r in rows if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "positive_pct": round(positive / total * 100, 1) if total else 0,
        "negative_pct": round(negative / total * 100, 1) if total else 0,
        "neutral_pct": round(neutral / total * 100, 1) if total else 0,
        "avg_rating": avg_rating,
    }


def _build_data(lgu_id: int | None = None) -> dict[str, Any]:
    """Build the full decision support data dict (called at most once per 10 min)."""
    weather = get_latest_weather(lgu_id)
    news = get_latest_news(limit=50)  # more for pagination
    trends = get_latest_trends(limit=10)

    event_feedbacks = get_event_feedbacks_for_display(limit=50)
    spot_feedbacks = get_spot_feedbacks_for_display(limit=50)
    online_reviews = get_online_reviews_for_display(limit=50)

    event_sentiment = get_event_sentiment_summary()
    fb_sentiment = get_feedback_sentiment_summary(lgu_id)
    ext_sentiment = get_external_review_sentiment_summary()

    spot_insights = get_spot_insights()
    event_insights = get_event_insights()

    weather_alert = get_weather_alert(weather)

    spot_combined_sentiment = {
        "total": fb_sentiment["total"] + ext_sentiment["total"],
        "positive": fb_sentiment["positive"] + ext_sentiment["positive"],
        "negative": fb_sentiment["negative"] + ext_sentiment["negative"],
        "neutral": fb_sentiment["neutral"] + ext_sentiment["neutral"],
        "positive_pct": round(
            (fb_sentiment["positive"] + ext_sentiment["positive"])
            / max(fb_sentiment["total"] + ext_sentiment["total"], 1)
            * 100,
            1,
        ),
        "negative_pct": round(
            (fb_sentiment["negative"] + ext_sentiment["negative"])
            / max(fb_sentiment["total"] + ext_sentiment["total"], 1)
            * 100,
            1,
        ),
        "neutral_pct": round(
            (fb_sentiment["neutral"] + ext_sentiment["neutral"])
            / max(fb_sentiment["total"] + ext_sentiment["total"], 1)
            * 100,
            1,
        ),
    }

    recommendations = _build_recommendations(
        fb_sentiment=fb_sentiment,
        ext_sentiment=ext_sentiment,
        event_sentiment=event_sentiment,
        weather_alert=weather_alert,
        trends=trends,
        news=news,
    )

    return {
        "weather": weather,
        "weather_alert": weather_alert,
        "news": news,
        "trends": trends,
        "event_feedbacks": event_feedbacks,
        "spot_feedbacks": spot_feedbacks,
        "online_reviews": online_reviews,
        "event_sentiment": event_sentiment,
        "feedback_sentiment": fb_sentiment,
        "ext_sentiment": ext_sentiment,
        "spot_combined_sentiment": spot_combined_sentiment,
        "spot_insights": spot_insights,
        "event_insights": event_insights,
        "recommendations": recommendations,
        "scraper_status": {
            "weather_ok": bool(weather),
            "news_ok": bool(news),
            "trends_ok": bool(trends),
            "reviews_ok": bool(online_reviews),
        },
    }


def get_decision_support_data(lgu_id: int | None = None) -> dict[str, Any]:
    """
    Return aggregated decision support data.
    Uses a 10-minute cache so the page loads in ~2s instead of 14s.
    Cache is invalidated when scrapers run (via invalidate_cache()).
    """
    global _CACHE
    now = _time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL:
        return _CACHE["data"]
    data = _build_data(lgu_id)
    _CACHE = {"data": data, "ts": now}
    return data


def invalidate_cache() -> None:
    """Call this after any scraper runs so the next page load gets fresh data."""
    global _CACHE
    _CACHE = {"data": None, "ts": 0.0}


def get_lgu_decision_support_data(lgu_id: int) -> dict[str, Any]:
    """
    Decision support data scoped to a single LGU (for lgu_admin role).
    Pulls province-wide scraped signals (weather, news, trends) but filters
    all feedback, sentiment, and insights to the LGU's own spots and events.
    """
    # Province-wide signals (cheap — already cached by the global build)
    province = get_decision_support_data(lgu_id=lgu_id)

    lgu_name = _get_lgu_name(lgu_id)

    # Scoped sentiment
    fb_sentiment = get_feedback_sentiment_summary(lgu_id)
    event_sentiment = _get_event_sentiment_for_lgu(lgu_id)
    ext_sentiment = _get_ext_sentiment_for_lgu(lgu_id)

    spot_combined_sentiment = {
        "total": fb_sentiment["total"] + ext_sentiment["total"],
        "positive": fb_sentiment["positive"] + ext_sentiment["positive"],
        "negative": fb_sentiment["negative"] + ext_sentiment["negative"],
        "neutral": fb_sentiment["neutral"] + ext_sentiment["neutral"],
        "positive_pct": round(
            (fb_sentiment["positive"] + ext_sentiment["positive"])
            / max(fb_sentiment["total"] + ext_sentiment["total"], 1) * 100, 1
        ),
        "negative_pct": round(
            (fb_sentiment["negative"] + ext_sentiment["negative"])
            / max(fb_sentiment["total"] + ext_sentiment["total"], 1) * 100, 1
        ),
        "neutral_pct": round(
            (fb_sentiment["neutral"] + ext_sentiment["neutral"])
            / max(fb_sentiment["total"] + ext_sentiment["total"], 1) * 100, 1
        ),
    }

    # Scoped insights — filter by lgu_name
    all_spot_insights = get_spot_insights()
    all_event_insights = get_event_insights()
    spot_insights = _filter_insights_by_lgu(all_spot_insights, lgu_name)
    event_insights = _filter_insights_by_lgu(all_event_insights, lgu_name)

    # Scoped feedbacks
    spot_feedbacks = _get_feedbacks_for_lgu(lgu_id)
    event_feedbacks = _get_event_feedbacks_for_lgu(lgu_id)
    online_reviews = _get_online_reviews_for_lgu(lgu_id)

    # Weather for this LGU only
    weather = [w for w in (province.get("weather") or []) if w.get("lgu_id") == lgu_id]
    weather_alert = get_weather_alert(weather) if weather else None

    recommendations = _build_recommendations(
        fb_sentiment=fb_sentiment,
        ext_sentiment=ext_sentiment,
        event_sentiment=event_sentiment,
        weather_alert=weather_alert,
        trends=province.get("trends") or [],
        news=province.get("news") or [],
    )

    return {
        "scope": "lgu",
        "lgu_id": lgu_id,
        "lgu_name": lgu_name,
        "weather": weather,
        "weather_alert": weather_alert,
        "news": province.get("news") or [],
        "trends": province.get("trends") or [],
        "event_feedbacks": event_feedbacks,
        "spot_feedbacks": spot_feedbacks,
        "online_reviews": online_reviews,
        "event_sentiment": event_sentiment,
        "feedback_sentiment": fb_sentiment,
        "ext_sentiment": ext_sentiment,
        "spot_combined_sentiment": spot_combined_sentiment,
        "spot_insights": spot_insights,
        "event_insights": event_insights,
        "recommendations": recommendations,
        "scraper_status": province.get("scraper_status") or {},
    }


def get_owner_decision_support_data(owner_id: str) -> dict[str, Any]:
    """
    Decision support data scoped to an establishment owner's own spot(s).
    Shows only their spot's insights, feedback, and sentiment.
    """
    spot_ids = _get_owner_spot_ids(owner_id)

    # Scoped sentiment
    fb_sentiment = _get_sentiment_for_spot_ids(spot_ids)
    # Owners don't have event feedback — use empty
    event_sentiment = {"total": 0, "positive": 0, "negative": 0, "neutral": 0,
                       "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0, "avg_rating": 0}
    ext_sentiment = {"total": 0, "positive": 0, "negative": 0, "neutral": 0,
                     "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0}

    spot_combined_sentiment = {
        "total": fb_sentiment["total"],
        "positive": fb_sentiment["positive"],
        "negative": fb_sentiment["negative"],
        "neutral": fb_sentiment["neutral"],
        "positive_pct": fb_sentiment["positive_pct"],
        "negative_pct": fb_sentiment["negative_pct"],
        "neutral_pct": fb_sentiment["neutral_pct"],
    }

    # Scoped insights
    all_spot_insights = get_spot_insights()
    spot_insights = _filter_insights_by_spot_ids(all_spot_insights, spot_ids)

    # Scoped feedbacks
    spot_feedbacks = _get_feedbacks_for_owner(spot_ids)
    online_reviews = _get_online_reviews_for_owner(spot_ids)

    recommendations = _build_recommendations(
        fb_sentiment=fb_sentiment,
        ext_sentiment=ext_sentiment,
        event_sentiment=event_sentiment,
        weather_alert=None,
        trends=[],
        news=[],
    )

    return {
        "scope": "owner",
        "spot_ids": list(spot_ids),
        "weather": [],
        "weather_alert": None,
        "news": [],
        "trends": [],
        "event_feedbacks": [],
        "spot_feedbacks": spot_feedbacks,
        "online_reviews": online_reviews,
        "event_sentiment": event_sentiment,
        "feedback_sentiment": fb_sentiment,
        "ext_sentiment": ext_sentiment,
        "spot_combined_sentiment": spot_combined_sentiment,
        "spot_insights": spot_insights,
        "event_insights": [],
        "recommendations": recommendations,
        "scraper_status": {},
    }


def _build_recommendations(
    fb_sentiment, ext_sentiment, event_sentiment, weather_alert, trends, news
) -> list[dict]:
    recs: list[dict] = []
    if weather_alert:
        recs.append(
            {
                "priority": "urgent",
                "icon": "bx-cloud-rain",
                "color": "danger",
                "title": "Adverse weather detected",
                "text": f"Conditions: {weather_alert}. Issue travel advisories.",
                "action": "View Weather",
                "action_url": "#weather",
            }
        )
    if fb_sentiment.get("negative_pct", 0) > 30:
        recs.append(
            {
                "priority": "high",
                "icon": "bx-error-circle",
                "color": "warning",
                "title": "High negative internal feedback",
                "text": f"{fb_sentiment['negative_pct']}% of spot feedback is negative. Review complaints.",
                "action": "View Spot Feedback",
                "action_url": "#spot-feedback",
            }
        )
    if (
        event_sentiment.get("total", 0) > 0
        and event_sentiment.get("negative_pct", 0) > 25
    ):
        recs.append(
            {
                "priority": "high",
                "icon": "bx-calendar-event",
                "color": "warning",
                "title": "Negative event feedback",
                "text": f"{event_sentiment['negative_pct']}% of event feedback is negative.",
                "action": "View Event Feedback",
                "action_url": "#event-feedback",
            }
        )
    if ext_sentiment.get("total", 0) > 0 and ext_sentiment.get("negative_pct", 0) > 25:
        recs.append(
            {
                "priority": "high",
                "icon": "bx-globe",
                "color": "warning",
                "title": "Negative online reviews",
                "text": f"{ext_sentiment['negative_pct']}% of scraped online reviews are negative.",
                "action": "View Online Reviews",
                "action_url": "#online-reviews",
            }
        )
    top_trend = next((t for t in trends if (t.get("interest_value") or 0) >= 30), None)
    if top_trend:
        recs.append(
            {
                "priority": "normal",
                "icon": "bx-trending-up",
                "color": "info",
                "title": f'Search interest: "{top_trend["keyword"]}"',
                "text": f"Google Trends: {top_trend['interest_value']}/100. Promote related spots now.",
                "action": "View Trends",
                "action_url": "#trends",
            }
        )
    neg_news = [n for n in news if n.get("sentiment") == "negative"]
    if len(neg_news) >= 3:
        recs.append(
            {
                "priority": "normal",
                "icon": "bx-news",
                "color": "secondary",
                "title": "Negative tourism news",
                "text": f"{len(neg_news)} recent articles are negative. Check headlines.",
                "action": "View News",
                "action_url": "#news",
            }
        )
    if fb_sentiment.get("positive_pct", 0) >= 70:
        recs.append(
            {
                "priority": "low",
                "icon": "bx-trophy",
                "color": "success",
                "title": "Strong tourist satisfaction",
                "text": f"{fb_sentiment['positive_pct']}% positive feedback. Feature top spots.",
                "action": "View Analytics",
                "action_url": "/dashboard/analytics",
            }
        )
    if not recs:
        recs.append(
            {
                "priority": "low",
                "icon": "bx-check-circle",
                "color": "success",
                "title": "No critical issues detected",
                "text": "Tourism indicators are stable. Refresh data below for latest signals.",
                "action": None,
                "action_url": None,
            }
        )
    order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    recs.sort(key=lambda r: order.get(r["priority"], 99))
    return recs


def get_scraper_last_run() -> dict[str, str | None]:
    def _latest(table: str) -> str | None:
        try:
            row = (
                get_supabase()
                .table(table)
                .select("scraped_at")
                .order("scraped_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            if row:
                val = str(row[0].get("scraped_at") or "")
                return val[:19].replace("T", " ") if val else None
        except Exception:
            pass
        return None

    return {
        "weather": _latest("scraped_weather"),
        "news": _latest("scraped_news"),
        "trends": _latest("scraped_trends"),
        "reviews": _latest("external_reviews"),
    }
