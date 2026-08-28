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
from services.scrapers.reviews_scraper import (
    get_event_feedbacks_for_display,
    get_online_reviews_for_display,
    get_spot_feedbacks_for_display,
)
from services.scrapers.sentiment_analyzer import (
    get_event_feedback_sentiment as get_event_sentiment_summary,
)
from services.scrapers.sentiment_analyzer import (
    classify_review_source,
    get_external_review_sentiment_summary,
    get_feedback_sentiment_summary,
)
from services.supabase_client import get_supabase

# ── Module-level cache (10-minute TTL), keyed per lgu_id (None = province-wide)
_CACHE: dict[int | None, dict[str, Any]] = {}
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


def _get_ext_sentiment_for_lgu(lgu_id: int, source_type: str | None = None) -> dict[str, Any]:
    """External review sentiment scoped to spots in a single LGU.
    source_type="social" restricts to Facebook posts only, excluding Google
    News coverage — see classify_review_source() in sentiment_analyzer.py."""
    try:
        rows = (
            get_supabase()
            .table("external_reviews")
            .select("sentiment, source, tourist_spots(lgu_id)")
            .execute()
            .data
            or []
        )
        rows = [r for r in rows if (r.get("tourist_spots") or {}).get("lgu_id") == lgu_id]
        if source_type:
            rows = [r for r in rows if classify_review_source(r.get("source")) == source_type]
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


def _group_insights_by_lgu(insights: list[dict]) -> list[dict[str, Any]]:
    """Group province-wide insight cards by LGU so super_admin/ltcato_staff
    get a scannable per-LGU breakdown instead of one long flat list — the
    LGU with the most severe issues sorts first."""
    groups: dict[str, dict[str, Any]] = {}
    for ins in insights:
        lgu_name = ins.get("lgu_name") or "Unknown"
        grp = groups.setdefault(
            lgu_name,
            {"lgu_name": lgu_name, "entries": [], "count": 0, "total_issues": 0, "high_negative_count": 0},
        )
        grp["entries"].append(ins)
        grp["count"] += 1
        grp["total_issues"] += len(ins.get("issues") or [])
        if (ins.get("negative_pct") or 0) > 50:
            grp["high_negative_count"] += 1
    return sorted(
        groups.values(),
        key=lambda g: (-g["high_negative_count"], -g["total_issues"], g["lgu_name"]),
    )


def _build_data(lgu_id: int | None = None) -> dict[str, Any]:
    """Build the full decision support data dict (called at most once per 10 min)."""
    event_feedbacks = get_event_feedbacks_for_display(limit=50)
    spot_feedbacks = get_spot_feedbacks_for_display(limit=50)
    online_reviews = get_online_reviews_for_display(limit=50)

    event_sentiment = get_event_sentiment_summary()
    fb_sentiment = get_feedback_sentiment_summary(lgu_id)
    ext_sentiment = get_external_review_sentiment_summary()
    social_sentiment = get_external_review_sentiment_summary(source_type="social")

    spot_insights = get_spot_insights()
    event_insights = get_event_insights()

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
        social_sentiment=social_sentiment,
        event_sentiment=event_sentiment,
    )

    return {
        "event_feedbacks": event_feedbacks,
        "spot_feedbacks": spot_feedbacks,
        "online_reviews": online_reviews,
        "event_sentiment": event_sentiment,
        "feedback_sentiment": fb_sentiment,
        "ext_sentiment": ext_sentiment,
        "spot_combined_sentiment": spot_combined_sentiment,
        "spot_insights": spot_insights,
        "event_insights": event_insights,
        "spot_insights_by_lgu": _group_insights_by_lgu(spot_insights),
        "event_insights_by_lgu": _group_insights_by_lgu(event_insights),
        "recommendations": recommendations,
        "scraper_status": {
            "reviews_ok": bool(online_reviews),
        },
    }


def get_decision_support_data(lgu_id: int | None = None) -> dict[str, Any]:
    """
    Return aggregated decision support data.
    Uses a 10-minute cache so the page loads in ~2s instead of 14s.
    Cache is invalidated when scrapers run (via invalidate_cache()).
    """
    now = _time.time()
    cached = _CACHE.get(lgu_id)
    if cached is not None and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]
    data = _build_data(lgu_id)
    _CACHE[lgu_id] = {"data": data, "ts": now}
    return data


def invalidate_cache() -> None:
    """Call this after any scraper runs so the next page load gets fresh data."""
    _CACHE.clear()


def get_lgu_decision_support_data(lgu_id: int) -> dict[str, Any]:
    """
    Decision support data scoped to a single LGU (for lgu_admin role).
    Filters all feedback, sentiment, and insights to the LGU's own spots
    and events.
    """
    # Cheap — already cached by the global build (used here for scraper_status only).
    province = get_decision_support_data(lgu_id=lgu_id)

    lgu_name = _get_lgu_name(lgu_id)

    # Scoped sentiment
    fb_sentiment = get_feedback_sentiment_summary(lgu_id)
    event_sentiment = _get_event_sentiment_for_lgu(lgu_id)
    ext_sentiment = _get_ext_sentiment_for_lgu(lgu_id)
    social_sentiment = _get_ext_sentiment_for_lgu(lgu_id, source_type="social")

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

    recommendations = _build_recommendations(
        fb_sentiment=fb_sentiment,
        social_sentiment=social_sentiment,
        event_sentiment=event_sentiment,
    )

    return {
        "scope": "lgu",
        "lgu_id": lgu_id,
        "lgu_name": lgu_name,
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
        social_sentiment=ext_sentiment,
        event_sentiment=event_sentiment,
    )

    return {
        "scope": "owner",
        "spot_ids": list(spot_ids),
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


# A percentage computed from too few reviews is noise, not signal — a
# threshold below is only allowed to trigger a recommendation once its
# source has at least this many reviews.
_MIN_SAMPLE = 10


def _build_recommendations(fb_sentiment, social_sentiment, event_sentiment) -> list[dict]:
    recs: list[dict] = []
    if fb_sentiment.get("total", 0) >= _MIN_SAMPLE and fb_sentiment.get("negative_pct", 0) > 30:
        recs.append(
            {
                "priority": "high",
                "icon": "bx-error-circle",
                "color": "warning",
                "title": "High negative internal feedback",
                "text": f"{fb_sentiment['negative_pct']}% of spot feedback is negative ({fb_sentiment['total']} reviews). Review complaints.",
                "action": "View Spot Feedback",
                "action_url": "#spot-feedback",
            }
        )
    if (
        event_sentiment.get("total", 0) >= _MIN_SAMPLE
        and event_sentiment.get("negative_pct", 0) > 25
    ):
        recs.append(
            {
                "priority": "high",
                "icon": "bx-calendar-event",
                "color": "warning",
                "title": "Negative event feedback",
                "text": f"{event_sentiment['negative_pct']}% of event feedback is negative ({event_sentiment['total']} reviews).",
                "action": "View Event Feedback",
                "action_url": "#event-feedback",
            }
        )
    if social_sentiment.get("total", 0) >= _MIN_SAMPLE and social_sentiment.get("negative_pct", 0) > 25:
        recs.append(
            {
                "priority": "high",
                "icon": "bx-globe",
                "color": "warning",
                "title": "Negative social media mentions",
                "text": f"{social_sentiment['negative_pct']}% of scraped Facebook posts about your spots are negative ({social_sentiment['total']} posts).",
                "action": "View Online Reviews",
                "action_url": "#online-reviews",
            }
        )
    if fb_sentiment.get("total", 0) >= _MIN_SAMPLE and fb_sentiment.get("positive_pct", 0) >= 70:
        recs.append(
            {
                "priority": "low",
                "icon": "bx-trophy",
                "color": "success",
                "title": "Strong tourist satisfaction",
                "text": f"{fb_sentiment['positive_pct']}% positive feedback ({fb_sentiment['total']} reviews). Feature top spots.",
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
        "reviews": _latest("external_reviews"),
    }


# Scraping loops over every spot in-scope with a network call per spot and
# hits a rate-limited third-party API (RapidAPI for Facebook), so opening
# the trigger to all dashboard roles needs a cooldown — otherwise several
# people clicking around the same time would each kick off a multi-minute
# scrape concurrently. The cooldown is scoped to match what scrape_reviews()
# actually scrapes (see routes/dashboard/actions.py): an lgu_admin's run
# only locks their own LGU, an owner's run only locks their own spots, and
# only the province-wide run (super_admin/ltcato_staff) locks everyone —
# otherwise one LGU's small scrape would block every unrelated LGU/owner too.
# Backed by external_reviews.scraped_at (not an in-memory timer) so it holds
# across multiple app workers/processes, not just within one.
SCRAPE_COOLDOWN_MINUTES = 20


def _latest_scraped_at(*, lgu_id: int | None = None, owner_id: str | None = None) -> str | None:
    """Latest external_reviews.scraped_at for the given scope.
    owner_id: one owner's spots. lgu_id: an LGU's spots + events (owners
    have no events, so owner_id never checks events). Both None: every row
    (province-wide)."""
    if lgu_id is None and owner_id is None:
        queries = [get_supabase().table("external_reviews").select("scraped_at")]
    elif owner_id is not None:
        queries = [
            get_supabase()
            .table("external_reviews")
            .select("scraped_at, tourist_spots!inner(owner_id)")
            .eq("tourist_spots.owner_id", owner_id)
        ]
    else:
        queries = [
            get_supabase()
            .table("external_reviews")
            .select("scraped_at, tourist_spots!inner(lgu_id)")
            .eq("tourist_spots.lgu_id", lgu_id),
            get_supabase()
            .table("external_reviews")
            .select("scraped_at, events!inner(lgu_id)")
            .eq("events.lgu_id", lgu_id),
        ]

    latest: str | None = None
    for q in queries:
        try:
            rows = q.order("scraped_at", desc=True).limit(1).execute().data or []
        except Exception:
            continue
        if rows:
            ts = str(rows[0].get("scraped_at") or "")
            if ts and (latest is None or ts > latest):
                latest = ts
    return latest


def get_scrape_cooldown_remaining_minutes(
    *, lgu_id: int | None = None, owner_id: str | None = None
) -> int:
    """Minutes until Scrape Reviews may run again for this scope, or 0 if
    it's fine now. Pass the same lgu_id/owner_id the scrape itself will be
    scoped to; omit both for the province-wide check."""
    last_run = _latest_scraped_at(lgu_id=lgu_id, owner_id=owner_id)
    if not last_run:
        return 0
    try:
        from datetime import datetime, timezone

        ts = last_run[:19].replace("T", " ")
        last_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
    except ValueError:
        return 0
    return max(0, round(SCRAPE_COOLDOWN_MINUTES - elapsed_minutes))
