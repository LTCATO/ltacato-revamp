"""
Tourist Decision Support Service
Provides personalised travel recommendations based on a tourist's own data:
  - saved spots & events
  - itinerary history
  - passport stamps
  - weather at their planned destinations
  - upcoming events near their saved spots
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase


# ── helpers ───────────────────────────────────────────────────────────────


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ── data collectors ───────────────────────────────────────────────────────


def _get_saved_spots(tourist_id: str) -> list[dict]:
    return _safe(
        lambda: (
            get_supabase()
            .table("spot_engagements")
            .select(
                "type, tourist_spots(id, name, lgu_id, rating, reviews_count,"
                " main_image_url, lgus(name))"
            )
            .eq("tourist_id", tourist_id)
            .eq("type", "bookmark")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        ),
        [],
    )


def _get_saved_events(tourist_id: str) -> list[dict]:
    return _safe(
        lambda: (
            get_supabase()
            .table("event_engagements")
            .select(
                "type, events(id, title, start_date, end_date, event_status,"
                " cover_image, lgu_id, lgus(name))"
            )
            .eq("tourist_id", tourist_id)
            .eq("type", "bookmark")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        ),
        [],
    )


def _get_itineraries(tourist_id: str) -> list[dict]:
    return _safe(
        lambda: (
            get_supabase()
            .table("itineraries")
            .select("id, title, start_date, end_date, trip_purpose, traveler_count")
            .eq("tourist_id", tourist_id)
            .order("start_date", desc=True)
            .limit(10)
            .execute()
            .data
            or []
        ),
        [],
    )


def _get_passport(tourist_id: str) -> dict | None:
    rows = _safe(
        lambda: (
            get_supabase()
            .table("tourist_passports")
            .select("id, passport_number, points")
            .eq("tourist_id", tourist_id)
            .limit(1)
            .execute()
            .data
            or []
        ),
        [],
    )
    return rows[0] if rows else None


def _get_stamp_count(passport_id: int) -> int:
    rows = _safe(
        lambda: (
            get_supabase()
            .table("passport_stamps")
            .select("id", count="exact")
            .eq("passport_id", passport_id)
            .execute()
        ),
        None,
    )
    if rows is None:
        return 0
    return getattr(rows, "count", 0) or len(getattr(rows, "data", []))


def _get_upcoming_events(lgu_ids: list[int], limit: int = 6) -> list[dict]:
    if not lgu_ids:
        return []
    return _safe(
        lambda: (
            get_supabase()
            .table("events")
            .select("id, title, start_date, end_date, cover_image, lgu_id, lgus(name)")
            .in_("lgu_id", lgu_ids)
            .eq("approval_status", "approved")
            .in_("event_status", ["upcoming", "ongoing"])
            .order("start_date")
            .limit(limit)
            .execute()
            .data
            or []
        ),
        [],
    )


def _get_weather_for_lgus(lgu_ids: list[int]) -> list[dict]:
    if not lgu_ids:
        return []
    return _safe(
        lambda: (
            get_supabase()
            .table("scraped_weather")
            .select(
                "lgu_id, weather_main, weather_description,"
                " temperature_celsius, humidity_percent, lgus(name)"
            )
            .in_("lgu_id", lgu_ids)
            .eq("is_forecast", False)
            .order("scraped_at", desc=True)
            .limit(len(lgu_ids) * 2)
            .execute()
            .data
            or []
        ),
        [],
    )


def _get_top_spots(lgu_ids: list[int], limit: int = 6) -> list[dict]:
    """Highly-rated spots in the tourist's areas of interest."""
    if not lgu_ids:
        return []
    return _safe(
        lambda: (
            get_supabase()
            .table("tourist_spots")
            .select("id, name, rating, reviews_count, main_image_url, lgu_id, lgus(name)")
            .in_("lgu_id", lgu_ids)
            .eq("approval_status", "approved")
            .order("rating", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        ),
        [],
    )


# ── recommendation builder ────────────────────────────────────────────────


def _build_tourist_recommendations(
    saved_spots: list[dict],
    saved_events: list[dict],
    itineraries: list[dict],
    passport: dict | None,
    stamp_count: int,
    upcoming_events: list[dict],
    weather_by_lgu: dict[int, dict],
) -> list[dict]:
    recs: list[dict] = []

    # Weather alerts for saved spot LGUs
    for lgu_id, w in weather_by_lgu.items():
        main = (w.get("weather_main") or "").lower()
        desc = w.get("weather_description") or ""
        lgu_name = (w.get("lgus") or {}).get("name") or f"LGU #{lgu_id}"
        if any(kw in main for kw in ("rain", "storm", "thunder", "drizzle", "snow")):
            recs.append(
                {
                    "priority": "urgent",
                    "icon": "ph-cloud-rain",
                    "color": "danger",
                    "title": f"Weather advisory — {lgu_name}",
                    "text": f"Current conditions: {desc}. Check your plans for spots in this area.",
                    "action": "View planner",
                    "action_url": "/planner",
                }
            )

    # Upcoming events near saved spots
    if upcoming_events:
        ev = upcoming_events[0]
        lgu_name = (ev.get("lgus") or {}).get("name") or ""
        recs.append(
            {
                "priority": "high",
                "icon": "ph-calendar-star",
                "color": "info",
                "title": f"Upcoming event: {ev['title']}",
                "text": f"Happening in {lgu_name} on {ev.get('start_date') or 'TBA'}. Add it to your itinerary.",
                "action": "View event",
                "action_url": f"/events/{ev['id']}",
            }
        )

    # Passport progress nudge
    if passport:
        if stamp_count == 0:
            recs.append(
                {
                    "priority": "normal",
                    "icon": "ph-identification-badge",
                    "color": "warning",
                    "title": "Start your Laguna Passport",
                    "text": "You have a passport but no stamps yet. Visit a spot and collect your first stamp.",
                    "action": "Browse spots",
                    "action_url": "/spots",
                }
            )
        elif stamp_count < 5:
            recs.append(
                {
                    "priority": "normal",
                    "icon": "ph-stamp",
                    "color": "info",
                    "title": f"{stamp_count} stamp{'s' if stamp_count != 1 else ''} collected",
                    "text": "Keep exploring Laguna to earn more passport stamps and points.",
                    "action": "Plan a trip",
                    "action_url": "/planner",
                }
            )
        else:
            recs.append(
                {
                    "priority": "low",
                    "icon": "ph-trophy",
                    "color": "success",
                    "title": f"Great explorer — {stamp_count} stamps",
                    "text": f"You have {passport.get('points', 0)} exploration points. Keep discovering Laguna.",
                    "action": "My profile",
                    "action_url": "/profile",
                }
            )

    # No saved spots nudge
    if not saved_spots:
        recs.append(
            {
                "priority": "normal",
                "icon": "ph-map-pin",
                "color": "info",
                "title": "Discover spots to visit",
                "text": "Bookmark tourist spots to get personalised weather and event alerts here.",
                "action": "Browse spots",
                "action_url": "/spots",
            }
        )

    # No itineraries nudge
    if not itineraries:
        recs.append(
            {
                "priority": "low",
                "icon": "ph-suitcase",
                "color": "info",
                "title": "Plan your first trip",
                "text": "Use the AI itinerary planner to build a personalised Laguna adventure.",
                "action": "Open planner",
                "action_url": "/planner",
            }
        )
    else:
        # Check for an active/upcoming itinerary
        from datetime import date as _date

        today = _date.today().isoformat()
        active = next(
            (
                t
                for t in itineraries
                if (t.get("end_date") or "9999") >= today
            ),
            None,
        )
        if active:
            recs.append(
                {
                    "priority": "low",
                    "icon": "ph-calendar-check",
                    "color": "success",
                    "title": f"Upcoming trip: {active['title']}",
                    "text": f"Starts {active.get('start_date') or 'soon'}. Check your itinerary for details.",
                    "action": "View itinerary",
                    "action_url": "/my-trips",
                }
            )

    if not recs:
        recs.append(
            {
                "priority": "low",
                "icon": "ph-check-circle",
                "color": "success",
                "title": "All clear",
                "text": "No alerts for your saved spots right now. Enjoy your travels!",
                "action": None,
                "action_url": None,
            }
        )

    order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    recs.sort(key=lambda r: order.get(r["priority"], 99))
    return recs


# ── public API ────────────────────────────────────────────────────────────


def get_tourist_decision_support(tourist_id: str) -> dict[str, Any]:
    """
    Return personalised decision support data for a logged-in tourist.
    Scoped to their own saved spots, events, itineraries, and passport.
    """
    saved_spot_rows = _get_saved_spots(tourist_id)
    saved_event_rows = _get_saved_events(tourist_id)
    itineraries = _get_itineraries(tourist_id)
    passport = _get_passport(tourist_id)
    stamp_count = _get_stamp_count(passport["id"]) if passport else 0

    # Collect LGU IDs from saved spots and events
    lgu_ids: list[int] = []
    saved_spots: list[dict] = []
    for row in saved_spot_rows:
        spot = row.get("tourist_spots") or {}
        if spot:
            saved_spots.append(spot)
            lid = spot.get("lgu_id")
            if lid and lid not in lgu_ids:
                lgu_ids.append(lid)

    saved_events: list[dict] = []
    for row in saved_event_rows:
        ev = row.get("events") or {}
        if ev:
            saved_events.append(ev)
            lid = ev.get("lgu_id")
            if lid and lid not in lgu_ids:
                lgu_ids.append(lid)

    upcoming_events = _get_upcoming_events(lgu_ids)
    weather_rows = _get_weather_for_lgus(lgu_ids)
    top_spots = _get_top_spots(lgu_ids)

    # Deduplicate weather by lgu_id (keep most recent)
    weather_by_lgu: dict[int, dict] = {}
    for w in weather_rows:
        lid = w.get("lgu_id")
        if lid and lid not in weather_by_lgu:
            weather_by_lgu[lid] = w

    recommendations = _build_tourist_recommendations(
        saved_spots=saved_spots,
        saved_events=saved_events,
        itineraries=itineraries,
        passport=passport,
        stamp_count=stamp_count,
        upcoming_events=upcoming_events,
        weather_by_lgu=weather_by_lgu,
    )

    return {
        "recommendations": recommendations,
        "saved_spots": saved_spots,
        "saved_events": saved_events,
        "itineraries": itineraries,
        "passport": passport,
        "stamp_count": stamp_count,
        "upcoming_events": upcoming_events,
        "weather_by_lgu": list(weather_by_lgu.values()),
        "top_spots": top_spots,
        "lgu_ids": lgu_ids,
    }
