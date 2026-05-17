"""
Build day-by-day itinerary plans from selected tourist spots and trip preferences.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

from services.planner_integrations import (
    SLOT_TIMES,
    clothing_tip,
    fetch_weather_forecast,
    parse_entrance_fee_estimate,
    travel_matrix_minutes,
)
from services.spots import get_categories, get_lgus

TRIP_PURPOSES = (
    ("vacation", "Vacation & leisure"),
    ("family", "Family trip"),
    ("adventure", "Adventure & outdoors"),
    ("educational", "Educational / heritage"),
    ("business", "Business / work"),
)

ROUTE_STYLES = (
    ("shortest", "Shortest travel time"),
    ("scenic", "Scenic route (spread across LGUs)"),
    ("compact", "Stay within fewer towns"),
)

PACE_OPTIONS = (
    ("relaxed", "Relaxed (2 stops / day)"),
    ("moderate", "Moderate (3 stops / day)"),
    ("packed", "Packed (4 stops / day)"),
)

PRIORITY_OPTIONS = (
    ("must_visit", "Must visit"),
    ("optional", "Optional"),
    ("skip_if_needed", "Skip if needed"),
)

MAX_SPOTS_PER_DAY = {"relaxed": 2, "moderate": 3, "packed": 4}


def planner_form_options() -> dict[str, Any]:
    return {
        "trip_purposes": TRIP_PURPOSES,
        "route_styles": ROUTE_STYLES,
        "pace_options": PACE_OPTIONS,
        "priority_options": PRIORITY_OPTIONS,
        "categories": get_categories(),
        "lgus": get_lgus(),
    }


def _spot_coords(spot: dict[str, Any]) -> tuple[float, float] | None:
    lat, lng = spot.get("latitude"), spot.get("longitude")
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def _order_spots_nearest_neighbor(
    spots: list[dict[str, Any]],
    matrix: list[list[int]],
) -> list[dict[str, Any]]:
    if len(spots) <= 1:
        return list(spots)
    remaining = set(range(len(spots)))
    order: list[int] = [0]
    remaining.remove(0)
    current = 0
    while remaining:
        nxt = min(remaining, key=lambda j: matrix[current][j])
        order.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return [spots[i] for i in order]


def _order_spots_scenic(spots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Interleave LGUs for variety."""
    by_lgu: dict[int | str, list[dict[str, Any]]] = {}
    for spot in spots:
        key = spot.get("lgu_id") or "unknown"
        by_lgu.setdefault(key, []).append(spot)
    ordered: list[dict[str, Any]] = []
    queues = list(by_lgu.values())
    idx = 0
    while any(queues):
        q = queues[idx % len(queues)]
        if q:
            ordered.append(q.pop(0))
        queues = [q for q in queues if q]
        idx += 1
    return ordered


def _trip_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def _gemini_tips(plan_summary: str) -> list[str]:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"')
    if not api_key:
        return []

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are Lara, Laguna Philippines tourism assistant. "
            "Given this trip plan summary, return exactly 4 short practical tips "
            "(one line each, no numbering, no markdown). Focus on Laguna travel, "
            "food, commute, and culture.\n\n"
            f"{plan_summary}"
        )
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in text.splitlines() if ln.strip()]
        return [ln for ln in lines if len(ln) > 10][:4]
    except Exception:
        return []


def generate_plan(
    *,
    title: str,
    spots: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    starting_point: str = "",
    traveler_count: int = 1,
    trip_purpose: str = "vacation",
    total_budget: float | None = None,
    pace: str = "moderate",
    route_style: str = "shortest",
    category_ids: list[int] | None = None,
    lgu_id: int | None = None,
    spot_priorities: dict[int, str] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    spot_priorities = spot_priorities or {}
    trip_days = _trip_dates(start_date, end_date)
    duration_days = len(trip_days)

    if not spots:
        return {
            "ok": False,
            "error": "Select at least one tourist spot to build your itinerary.",
        }

    if duration_days < 1:
        return {
            "ok": False,
            "error": "End date must be on or after the start date.",
        }

    # Filter optional spots if too many for trip length
    max_stops = MAX_SPOTS_PER_DAY.get(pace, 3) * duration_days
    must = [s for s in spots if spot_priorities.get(s["id"], "must_visit") == "must_visit"]
    optional = [s for s in spots if s not in must]
    ordered_pool = must + optional
    if len(ordered_pool) > max_stops:
        ordered_pool = ordered_pool[:max_stops]

    coords_list: list[tuple[float, float]] = []
    valid_spots: list[dict[str, Any]] = []
    for spot in ordered_pool:
        c = _spot_coords(spot)
        if c:
            coords_list.append(c)
            valid_spots.append(spot)
        else:
            valid_spots.append(spot)

    matrix: list[list[int]] = []
    if len(coords_list) >= 2:
        matrix = travel_matrix_minutes(coords_list)
        coord_index = {id(s): i for i, s in enumerate(valid_spots) if _spot_coords(s)}
        indexed = [(i, s) for i, s in enumerate(valid_spots) if _spot_coords(s)]
        if route_style == "scenic":
            routed = _order_spots_scenic(valid_spots)
        elif indexed:
            sub_spots = [s for _, s in indexed]
            sub_matrix = travel_matrix_minutes([_spot_coords(s) for s in sub_spots if _spot_coords(s)])
            sub_ordered = _order_spots_nearest_neighbor(sub_spots, sub_matrix)
            no_coord = [s for s in valid_spots if not _spot_coords(s)]
            routed = sub_ordered + no_coord
        else:
            routed = valid_spots
    else:
        routed = _order_spots_scenic(valid_spots) if route_style == "scenic" else valid_spots

    per_day = MAX_SPOTS_PER_DAY.get(pace, 3)
    day_buckets: list[list[dict[str, Any]]] = [[] for _ in trip_days]
    for idx, spot in enumerate(routed):
        day_buckets[idx % len(trip_days)].append(spot)

    # Weather centered on first geocoded spot or Laguna
    center = _spot_coords(routed[0]) if routed else None
    weather = fetch_weather_forecast(
        lat=center[0] if center else None,
        lon=center[1] if center else None,
        start=start_date,
        end=end_date,
    )

    slots = ["morning", "afternoon", "evening"]
    slot_idx = 0
    total_estimated = 0.0
    days_out: list[dict[str, Any]] = []

    prev_coord_idx = -1
    coord_spots = [s for s in routed if _spot_coords(s)]

    for day_num, (activity_date, day_spots) in enumerate(zip(trip_days, day_buckets), start=1):
        day_key = activity_date.isoformat()
        forecast = weather.get("daily", {}).get(day_key)
        stops: list[dict[str, Any]] = []

        for spot in day_spots:
            time_slot = slots[slot_idx % len(slots)]
            slot_idx += 1
            priority = spot_priorities.get(spot["id"], "must_visit")
            fee = parse_entrance_fee_estimate(spot.get("entrance_fees"))
            cost = fee * max(1, traveler_count)
            total_estimated += cost

            travel_minutes = 0
            c = _spot_coords(spot)
            if c and prev_coord_idx >= 0 and matrix:
                try:
                    pi = coord_spots.index(spot) if spot in coord_spots else -1
                    if pi > 0:
                        travel_minutes = matrix[pi - 1][pi]
                except (ValueError, IndexError):
                    travel_minutes = 0
            if spot in coord_spots:
                prev_coord_idx = coord_spots.index(spot)

            lgu = spot.get("lgus") or {}
            cat = spot.get("attraction_categories") or {}
            stops.append(
                {
                    "tourist_spot_id": spot["id"],
                    "name": spot.get("name"),
                    "description": (spot.get("hook_text") or spot.get("description") or "")[:280],
                    "main_image_url": spot.get("main_image_url"),
                    "address": spot.get("address"),
                    "lgu_name": lgu.get("name") if isinstance(lgu, dict) else "Laguna",
                    "category_name": cat.get("name") if isinstance(cat, dict) else "",
                    "latitude": spot.get("latitude"),
                    "longitude": spot.get("longitude"),
                    "opening_hours": spot.get("opening_hours"),
                    "entrance_fees": spot.get("entrance_fees"),
                    "food_options": spot.get("food_options"),
                    "rating": spot.get("rating"),
                    "reviews_count": spot.get("reviews_count"),
                    "day_number": day_num,
                    "activity_date": day_key,
                    "activity_time": SLOT_TIMES.get(time_slot, "09:00"),
                    "time_slot": time_slot,
                    "priority": priority,
                    "estimated_cost": cost,
                    "travel_minutes": travel_minutes,
                    "transportation": "Private car / ride-hail recommended between stops",
                    "notes": "",
                }
            )

        days_out.append(
            {
                "day_number": day_num,
                "activity_date": day_key,
                "label": activity_date.strftime("%A, %b %d"),
                "weather": forecast,
                "clothing_tip": clothing_tip(forecast),
                "stops": stops,
            }
        )

    budget_remaining = None
    if total_budget is not None and total_budget > 0:
        budget_remaining = round(total_budget - total_estimated, 2)

    summary = (
        f"Trip: {title}; {duration_days} days; {len(routed)} spots; "
        f"purpose={trip_purpose}; travelers={traveler_count}; starting={starting_point or 'Laguna'}."
    )
    smart_tips = _gemini_tips(summary)
    if not smart_tips:
        smart_tips = [
            "Start early on weekends — popular spots like Pagsanjan and Los Baños get busy by mid-morning.",
            "Keep cash for entrance fees; not all municipalities accept cards at gates.",
            "Check opening hours before you leave — some heritage sites close at noon.",
            "Try local specialties in each town (buko pie, kesong puti, espasol) near your route.",
        ]

    return {
        "ok": True,
        "title": title,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "duration_days": duration_days,
        "starting_point": starting_point,
        "traveler_count": traveler_count,
        "trip_purpose": trip_purpose,
        "total_budget": total_budget,
        "estimated_expense": round(total_estimated, 2),
        "budget_remaining": budget_remaining,
        "pace": pace,
        "route_style": route_style,
        "category_ids": category_ids or [],
        "lgu_id": lgu_id,
        "notes": notes,
        "days": days_out,
        "weather": weather,
        "smart_tips": smart_tips,
        "timezone": "Asia/Manila",
        "currency": "PHP",
        "emergency": {
            "police": "911",
            "fire": "911",
            "medical": "911",
            "tourist_hotline": "Contact LTCATO provincial office during business hours",
        },
        "transport_cards": [
            {
                "name": "Beep Card / stored-value",
                "detail": "Useful if your route includes Metro Manila connections to Laguna.",
            },
            {
                "name": "Jeepney & tricycle cash",
                "detail": "Have small bills for short hops between spots within municipalities.",
            },
        ],
    }
