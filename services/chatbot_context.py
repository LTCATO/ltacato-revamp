"""
Intent-scoped, permission-aware context builder for LARA.

Replaces the old _build_db_context(), which always ran every query
regardless of what was asked. Here, only the branches matching the
classified intent(s) run, and every branch is scoped by the caller-supplied
`scope` dict (see services/chatbot_scope.py) — never by anything from the
request body.

Each branch is independently cached with a TTL appropriate to how often
that data actually changes (see the per-cache ttl_seconds below), and cache
keys include the scope (lgu_id/owner_id) so different tenants never share
a cached answer.
"""

from __future__ import annotations

from typing import Any

from services.chatbot_analytics_helpers import compute_growth_pct
from services.chatbot_intent import (
    INTENT_ARRIVAL_ANALYTICS,
    INTENT_DECISION_SUPPORT,
    INTENT_EVENTS,
    INTENT_FAQ,
    INTENT_GENERAL,
    INTENT_LGUS,
    INTENT_SPOTS,
)
from services.chatbot_knowledge import list_knowledge
from services.dashboard_analytics import get_analytics_overview, get_establishment_analytics
from services.events import _compute_event_status, list_events
from services.lgus import list_lgus
from services.spots import list_spots, list_spots_for_dashboard
from services.ttl_cache import TTLCache

_NON_TOURIST_ROLES = {"lgu_admin", "ltcato_staff", "super_admin", "establishment_owner"}

_spots_cache = TTLCache(max_size=200, ttl_seconds=300)
_events_cache = TTLCache(max_size=100, ttl_seconds=300)
_lgus_cache = TTLCache(max_size=20, ttl_seconds=900)
_faq_cache = TTLCache(max_size=10, ttl_seconds=1800)
_analytics_cache = TTLCache(max_size=100, ttl_seconds=60)

_CACHES = {
    "spots": _spots_cache,
    "events": _events_cache,
    "lgus": _lgus_cache,
    "faq": _faq_cache,
    "arrival_analytics": _analytics_cache,
}


def invalidate(kind: str) -> None:
    cache = _CACHES.get(kind)
    if cache:
        cache.invalidate()
    if kind == "spots":
        _spot_directory_cache.invalidate()


def _spot_card_fields(spot: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": spot.get("id"),
        "name": spot.get("name"),
        "hook_text": spot.get("hook_text"),
        "address": spot.get("address"),
        "rating": spot.get("rating"),
        "reviews_count": spot.get("reviews_count"),
        "main_image_url": spot.get("main_image_url"),
        "municipality": (spot.get("lgus") or {}).get("name"),
        "category": (spot.get("attraction_categories") or {}).get("name"),
        "approval_status": spot.get("approval_status"),
        "best_time_to_visit": spot.get("best_time_to_visit"),
    }


def _get_spots(scope: dict[str, Any]) -> list[dict[str, Any]]:
    role = scope.get("role")
    key = f"role={role}:lgu={scope.get('lgu_id')}:owner={scope.get('owner_id')}"
    cached = _spots_cache.get(key)
    if cached is not None:
        return cached

    try:
        if role == "establishment_owner":
            spot_ids = scope.get("spot_ids") or []
            rows = list_spots_for_dashboard(owner_id=scope.get("owner_id"), limit=20) if spot_ids else []
        else:
            rows, _total = list_spots(lgu_id=scope.get("lgu_id"), sort="rating", page=1)
        result = [_spot_card_fields(r) for r in rows[:20]]
    except Exception:
        result = []

    _spots_cache.set(key, result)
    return result


def _event_card_fields(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"),
        "title": event.get("title"),
        "short_description": event.get("short_description"),
        "start_date": event.get("start_date"),
        "end_date": event.get("end_date"),
        "venue_name": event.get("venue_name"),
        "cover_image": event.get("cover_image"),
        "municipality": (event.get("lgus") or {}).get("name"),
        "status": _compute_event_status(event),
    }


def _get_events(scope: dict[str, Any]) -> list[dict[str, Any]]:
    key = f"lgu={scope.get('lgu_id')}"
    cached = _events_cache.get(key)
    if cached is not None:
        return cached

    try:
        rows = list_events(public_approved_only=True, lgu_id=scope.get("lgu_id"), limit=30)
        active = [e for e in rows if _compute_event_status(e) in ("upcoming", "ongoing")]
        result = [_event_card_fields(e) for e in active[:15]]
    except Exception:
        result = []

    _events_cache.set(key, result)
    return result


def _get_lgus() -> list[dict[str, Any]]:
    cached = _lgus_cache.get("all")
    if cached is not None:
        return cached
    try:
        rows, _summary = list_lgus()
        result = [{"id": r.get("id"), "name": r.get("name"), "type": r.get("type_label")} for r in rows]
    except Exception:
        result = []
    _lgus_cache.set("all", result)
    return result


_spot_directory_cache = TTLCache(max_size=1, ttl_seconds=300)
_lgu_directory_cache = TTLCache(max_size=1, ttl_seconds=900)


def get_spot_directory() -> list[dict[str, Any]]:
    """All approved spots with coordinates — used for route/distance resolution."""
    cached = _spot_directory_cache.get("all")
    if cached is not None:
        return cached
    try:
        from services.supabase_client import get_supabase

        rows = (
            get_supabase()
            .table("tourist_spots")
            .select("id, name, lgu_id, latitude, longitude, lgus(name)")
            .eq("approval_status", "approved")
            .execute()
            .data
            or []
        )
        result = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "lgu_id": r.get("lgu_id"),
                "municipality": (r.get("lgus") or {}).get("name"),
                "latitude": r.get("latitude"),
                "longitude": r.get("longitude"),
            }
            for r in rows
        ]
    except Exception:
        result = []
    _spot_directory_cache.set("all", result)
    return result


def get_lgu_directory() -> list[dict[str, Any]]:
    """All LGUs with coordinates — used for route/distance resolution."""
    cached = _lgu_directory_cache.get("all")
    if cached is not None:
        return cached
    try:
        from services.supabase_client import get_supabase

        rows = (
            get_supabase()
            .table("lgus")
            .select("id, name, latitude, longitude")
            .execute()
            .data
            or []
        )
        result = list(rows)
    except Exception:
        result = []
    _lgu_directory_cache.set("all", result)
    return result


def invalidate_directories() -> None:
    _spot_directory_cache.invalidate()
    _lgu_directory_cache.invalidate()


def _get_faq() -> list[dict[str, Any]]:
    cached = _faq_cache.get("approved")
    if cached is not None:
        return cached
    try:
        rows = list_knowledge(approval_status="approved", limit=20)
        result = [{"question": r.get("question"), "answer": r.get("answer")} for r in rows]
    except Exception:
        result = []
    _faq_cache.set("approved", result)
    return result


def _get_arrival_analytics(scope: dict[str, Any]) -> dict[str, Any] | None:
    role = scope.get("role")
    if role not in _NON_TOURIST_ROLES:
        return None

    # lgu_admin must have a resolved lgu_id — an unassigned admin gets no
    # data rather than silently falling back to province-wide numbers.
    if role == "lgu_admin" and not scope.get("lgu_id"):
        return None
    # establishment_owner must have a resolved owner_id.
    if role == "establishment_owner" and not scope.get("owner_id"):
        return None

    key = f"role={role}:lgu={scope.get('lgu_id')}:owner={scope.get('owner_id')}"
    cached = _analytics_cache.get(key)
    if cached is not None:
        return cached

    try:
        if role == "establishment_owner":
            overview = get_establishment_analytics(owner_id=scope.get("owner_id"))
            result = {
                "scope": "establishment",
                "visitors_this_month": overview.get("visitors_this_month"),
                "reports_submitted": overview.get("reports_submitted"),
                "pending_reports": overview.get("pending_reports"),
                "monthly_trend": overview.get("monthly_trend"),
                "growth": compute_growth_pct(overview.get("monthly_trend") or []),
            }
        elif role == "lgu_admin":
            overview = get_analytics_overview(lgu_id=scope.get("lgu_id"))
            result = {
                "scope": "lgu",
                "monthly_arrival_total": overview.get("monthly_arrival_total"),
                "monthly_trend": overview.get("monthly_trend"),
                "spot_ranking": overview.get("spot_ranking"),
                "pending_lgu_spots": overview.get("pending_lgu_spots"),
                "pending_ltcato_spots": overview.get("pending_ltcato_spots"),
                "pending_events": overview.get("pending_events"),
                "growth": compute_growth_pct(overview.get("monthly_trend") or []),
                # arrival_by_lgu from get_analytics_overview is always
                # province-wide regardless of lgu_id — never surface it to
                # an lgu_admin, it would leak every other LGU's numbers.
                "arrival_by_lgu": None,
            }
        else:  # ltcato_staff / super_admin — province-wide
            overview = get_analytics_overview(lgu_id=None)
            result = {
                "scope": "province",
                "monthly_arrival_total": overview.get("monthly_arrival_total"),
                "monthly_trend": overview.get("monthly_trend"),
                "spot_ranking": overview.get("spot_ranking"),
                "pending_lgu_spots": overview.get("pending_lgu_spots"),
                "pending_ltcato_spots": overview.get("pending_ltcato_spots"),
                "pending_events": overview.get("pending_events"),
                "growth": compute_growth_pct(overview.get("monthly_trend") or []),
                "arrival_by_lgu": overview.get("arrival_by_lgu"),
                "lgu_count": overview.get("lgu_count"),
            }
    except Exception:
        result = None

    _analytics_cache.set(key, result)
    return result


def _get_decision_support(scope: dict[str, Any]) -> dict[str, Any] | None:
    role = scope.get("role")
    if role not in _NON_TOURIST_ROLES:
        return None

    from services.decision_support_service import (
        get_decision_support_data,
        get_lgu_decision_support_data,
        get_owner_decision_support_data,
    )

    try:
        if role == "establishment_owner":
            owner_id = scope.get("owner_id")
            if not owner_id:
                return None
            data = get_owner_decision_support_data(owner_id)
        elif role == "lgu_admin":
            lgu_id = scope.get("lgu_id")
            if not lgu_id:
                return None
            data = get_lgu_decision_support_data(lgu_id)
        else:
            data = get_decision_support_data(lgu_id=None)

        return {
            "scope": data.get("scope"),
            "sentiment": data.get("spot_combined_sentiment") or data.get("feedback_sentiment"),
            "spot_insights": (data.get("spot_insights") or [])[:5],
            "recommendations": (data.get("recommendations") or [])[:5],
            "recent_feedbacks": [
                {
                    "guest_name": f.get("guest_name"),
                    "rating": f.get("rating"),
                    "comments": f.get("comments"),
                }
                for f in (data.get("spot_feedbacks") or [])[:5]
            ],
        }
    except Exception:
        return None


def build_context(intents: list[str], scope: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}

    if INTENT_SPOTS in intents:
        context["spots"] = _get_spots(scope)
    if INTENT_EVENTS in intents:
        context["events"] = _get_events(scope)
    if INTENT_LGUS in intents:
        context["lgus"] = _get_lgus()
    if INTENT_FAQ in intents:
        context["faq"] = _get_faq()
    if INTENT_ARRIVAL_ANALYTICS in intents:
        analytics = _get_arrival_analytics(scope)
        if analytics is not None:
            context["arrival_analytics"] = analytics
    if INTENT_DECISION_SUPPORT in intents:
        decision_support = _get_decision_support(scope)
        if decision_support is not None:
            context["decision_support"] = decision_support

    if intents == [INTENT_GENERAL] or not context:
        # Small default context for greetings/small talk — a light teaser,
        # not the old full 4-query dump.
        context["spots"] = _get_spots(scope)[:6]
        context["events"] = _get_events(scope)[:4]
        context["faq"] = _get_faq()[:5]

    return context
