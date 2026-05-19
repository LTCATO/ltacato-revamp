"""
Build day-by-day itinerary plans from selected tourist spots and trip preferences.

Key design decisions:
- Every day is filled with a complete timeline of activities (travel, explore, eat, rest)
  regardless of how many spots are selected.
- Budget is respected: dining/accommodation costs are scaled to fit within the budget.
- Nearby food and hotel suggestions are fetched at generation time via Mapbox Geocoding
  so each stop gets its own real nearby results.
- The "priority" badge is no longer shown on stops.
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
import math
from datetime import date, timedelta
from typing import Any

from services.planner_integrations import (
    clothing_tip,
    fetch_weather_forecast,
    haversine_km,
    parse_entrance_fee_estimate,
    travel_matrix_minutes,
    _http_get_json,
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
    ("relaxed", "Relaxed (2 spots / day)"),
    ("moderate", "Moderate (3 spots / day)"),
    ("packed", "Packed (4 spots / day)"),
)

PRIORITY_OPTIONS = (
    ("must_visit", "Must visit"),
    ("optional", "Optional"),
    ("skip_if_needed", "Skip if needed"),
)

# Max tourist-spot visits per day (not counting meals/travel/rest)
MAX_SPOTS_PER_DAY = {"relaxed": 2, "moderate": 3, "packed": 4}

# Minutes spent at each spot type
VISIT_DURATION = {"relaxed": 150, "moderate": 120, "packed": 90}

# Default meal budget per person (PHP)
MEAL_BUDGET_PER_PERSON = 300
ACCOMMODATION_BUDGET_DEFAULT = 2000


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


def _fmt_time(total_mins: int) -> str:
    """Return time in 12-hour AM/PM format, e.g. '8:45 AM', '1:00 PM'."""
    h24 = (total_mins // 60) % 24
    m = total_mins % 60
    period = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {period}"


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


def _fetch_nearby_places(lat: float, lng: float, place_type: str, limit: int = 3) -> list[dict[str, Any]]:
    """
    Fetch nearby restaurants or hotels using Mapbox Geocoding API.
    Uses a tight bounding box (~15 km radius) around the spot to avoid
    returning results from distant cities.
    Returns a list of dicts with name, address, distance_km — sorted by distance,
    only including results within 15 km.
    """
    token = (os.getenv("MAP_API_KEY") or "").strip()
    if not token or lat is None or lng is None:
        return []

    # Build a ~15 km bounding box (roughly 0.135 degrees lat/lng per 15 km)
    delta = 0.135
    bbox = f"{lng - delta},{lat - delta},{lng + delta},{lat + delta}"

    query = "restaurant" if place_type == "dining" else "hotel"
    params = urllib.parse.urlencode({
        "proximity": f"{lng},{lat}",
        "bbox": bbox,
        "limit": limit + 5,  # fetch extra, then filter by distance
        "country": "PH",
        "access_token": token,
    })
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{urllib.parse.quote(query)}.json?{params}"
    data = _http_get_json(url)
    results = []
    for f in (data or {}).get("features") or []:
        coords = f.get("geometry", {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        flng, flat = coords[0], coords[1]
        dist = haversine_km(lat, lng, flat, flng)
        # Hard filter: only include results within 15 km
        if dist > 15.0:
            continue
        name = f.get("text") or "Unknown"
        full = f.get("place_name") or ""
        address = full.replace(name + ", ", "").strip()
        results.append({
            "name": name,
            "address": address,
            "distance_km": round(dist, 1),
        })
    # Sort by distance and return closest `limit` results
    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


def _build_full_day_timeline(
    *,
    day_num: int,
    activity_date: date,
    day_spots: list[dict[str, Any]],
    departure_time: str,
    return_time: str,
    traveler_count: int,
    pace: str,
    duration_days: int,
    is_last_day: bool,
    coord_spots: list[dict[str, Any]],
    matrix: list[list[int]],
    spot_priorities: dict[int, str],
    remaining_budget: float | None,
    meal_budget_per_person: float,
    accommodation_budget: float,
    forecast: dict | None,
) -> tuple[list[dict[str, Any]], float]:
    """
    Build a complete day timeline with travel, spot visits, meals, and rest blocks.
    Returns (stops_list, total_cost_for_day).
    """
    day_key = activity_date.isoformat()
    day_label = activity_date.strftime("%A, %b %d")

    try:
        dh, dm = map(int, departure_time.split(":"))
    except ValueError:
        dh, dm = 8, 0
    try:
        rh, rm = map(int, return_time.split(":"))
    except ValueError:
        rh, rm = 18, 0

    start_mins = dh * 60 + dm
    end_mins = rh * 60 + rm
    total_day_mins = end_mins - start_mins
    visit_duration = VISIT_DURATION.get(pace, 120)

    stops: list[dict[str, Any]] = []
    current_mins = start_mins
    day_cost = 0.0
    added_lunch = False
    added_dinner = False

    # ── Helper: add a non-spot activity block ─────────────────────────────────
    def add_activity(atype: str, name: str, desc: str, icon_hint: str,
                     duration_mins: int, cost: float = 0.0,
                     lat: float | None = None, lng: float | None = None,
                     lgu_name: str = "", nearby: list | None = None):
        nonlocal current_mins, day_cost
        stops.append({
            "tourist_spot_id": None,
            "type": atype,
            "name": name,
            "description": desc,
            "icon_hint": icon_hint,
            "lgu_name": lgu_name,
            "latitude": lat,
            "longitude": lng,
            "activity_date": day_key,
            "activity_time": _fmt_time(current_mins),
            "duration_mins": duration_mins,
            "estimated_cost": cost,
            "nearby_places": nearby or [],
            "notes": "",
        })
        day_cost += cost
        current_mins += duration_mins

    # ── Opening block: travel from starting point / hotel ─────────────────────
    if day_num == 1:
        add_activity(
            "travel", "Depart & Head Out",
            "Start your journey! Load up on snacks, fill up the tank, and hit the road early to beat traffic.",
            "ph-car", duration_mins=0,
        )
    else:
        add_activity(
            "travel", "Morning Prep & Check-out",
            "Have breakfast at your accommodation, pack up, and prepare for today's adventures.",
            "ph-coffee", duration_mins=30,
        )

    # ── Breakfast (only if departure is before 9 AM) ───────────────────────────
    if start_mins < 9 * 60:
        meal_cost = meal_budget_per_person * traveler_count * 0.6
        if remaining_budget is not None:
            meal_cost = min(meal_cost, remaining_budget * 0.08)
        meal_cost = max(50 * traveler_count, meal_cost)
        bfast_lat, bfast_lng, bfast_lgu = None, None, ""
        if day_spots:
            c = _spot_coords(day_spots[0])
            if c:
                bfast_lat, bfast_lng = c
                bfast_lgu = (day_spots[0].get("lgus") or {}).get("name") or ""
        nearby_breakfast = _fetch_nearby_places(bfast_lat, bfast_lng, "dining", 3) if bfast_lat else []
        add_activity(
            "dining", "Breakfast",
            "Fuel up before exploring! Try local kakanin, tapsilog, or fresh pandesal near your first stop.",
            "ph-coffee", duration_mins=45,
            cost=round(meal_cost, 0),
            lat=bfast_lat, lng=bfast_lng, lgu_name=bfast_lgu,
            nearby=nearby_breakfast,
        )

    # ── Main spot visits ───────────────────────────────────────────────────────
    for spot_idx, spot in enumerate(day_spots):
        lgu = spot.get("lgus") or {}
        cat = spot.get("attraction_categories") or {}
        lgu_name = lgu.get("name") if isinstance(lgu, dict) else "Laguna"
        cat_name = cat.get("name") if isinstance(cat, dict) else ""
        c = _spot_coords(spot)
        spot_lat = c[0] if c else None
        spot_lng = c[1] if c else None

        # Travel to this spot
        travel_mins = 0
        if spot_idx > 0 or day_num > 1:
            prev_spot = day_spots[spot_idx - 1] if spot_idx > 0 else None
            if prev_spot and c:
                pc = _spot_coords(prev_spot)
                if pc:
                    dist_km = haversine_km(pc[0], pc[1], c[0], c[1])
                    travel_mins = max(5, int((dist_km / 28.0) * 60))
            elif c and day_num > 1:
                travel_mins = 20  # default from hotel

        if travel_mins > 0:
            add_activity(
                "travel",
                f"Travel to {spot.get('name', 'next stop')}",
                f"~{travel_mins} min drive. {'Enjoy the scenic Laguna roads!' if travel_mins > 20 else 'Short hop — enjoy the view!'}",
                "ph-car", duration_mins=travel_mins,
                lat=spot_lat, lng=spot_lng, lgu_name=lgu_name,
            )

        # Inject lunch between 11:30 AM and 2:00 PM, before visiting the spot
        if not added_lunch and 11 * 60 + 30 <= current_mins <= 14 * 60:
            meal_cost = meal_budget_per_person * traveler_count
            if remaining_budget is not None:
                meal_cost = min(meal_cost, remaining_budget * 0.12)
            meal_cost = max(100 * traveler_count, meal_cost)
            nearby_lunch = _fetch_nearby_places(spot_lat, spot_lng, "dining", 3) if spot_lat else []
            add_activity(
                "dining", "Lunch Break",
                f"Time to eat! Look for local Laguna specialties near {lgu_name} — try buko pie, kesong puti, or fresh lake fish.",
                "ph-fork-knife", duration_mins=60,
                cost=round(meal_cost, 0),
                lat=spot_lat, lng=spot_lng, lgu_name=lgu_name,
                nearby=nearby_lunch,
            )
            added_lunch = True

        # The spot visit itself
        fee = parse_entrance_fee_estimate(spot.get("entrance_fees"))
        spot_cost = fee * max(1, traveler_count)
        if remaining_budget is not None and spot_cost > 0:
            spot_cost = min(spot_cost, remaining_budget * 0.25)

        stops.append({
            "tourist_spot_id": spot["id"],
            "type": "spot",
            "name": spot.get("name"),
            "description": (spot.get("hook_text") or spot.get("description") or "")[:280],
            "main_image_url": spot.get("main_image_url"),
            "address": spot.get("address"),
            "lgu_name": lgu_name,
            "category_name": cat_name,
            "latitude": spot_lat,
            "longitude": spot_lng,
            "opening_hours": spot.get("opening_hours"),
            "entrance_fees": spot.get("entrance_fees"),
            "food_options": spot.get("food_options"),
            "rating": spot.get("rating"),
            "reviews_count": spot.get("reviews_count"),
            "day_number": day_num,
            "activity_date": day_key,
            "activity_time": _fmt_time(current_mins),
            "duration_mins": visit_duration,
            "time_slot": "morning" if current_mins < 12 * 60 else ("afternoon" if current_mins < 17 * 60 else "evening"),
            "estimated_cost": round(spot_cost, 0),
            "travel_minutes": travel_mins,
            "transportation": "Private car / ride-hail recommended",
            "notes": "",
            "nearby_places": [],
        })
        day_cost += spot_cost
        current_mins += visit_duration

    # ── Ensure lunch is added even if spots ended before 11:30 ────────────────
    if not added_lunch:
        # Force lunch at 12:00 PM if we haven't had it yet
        lunch_time = max(current_mins, 12 * 60)
        current_mins = lunch_time
        last_stop = next((s for s in reversed(stops) if s.get("latitude")), None)
        lunch_lat = last_stop.get("latitude") if last_stop else None
        lunch_lng = last_stop.get("longitude") if last_stop else None
        lunch_lgu = last_stop.get("lgu_name", "") if last_stop else ""
        meal_cost = meal_budget_per_person * traveler_count
        if remaining_budget is not None:
            meal_cost = min(meal_cost, remaining_budget * 0.12)
        meal_cost = max(100 * traveler_count, meal_cost)
        nearby_lunch = _fetch_nearby_places(lunch_lat, lunch_lng, "dining", 3) if lunch_lat else []
        add_activity(
            "dining", "Lunch Break",
            f"Time to eat! Look for local Laguna specialties{' near ' + lunch_lgu if lunch_lgu else ''} — try buko pie, kesong puti, or fresh lake fish.",
            "ph-fork-knife", duration_mins=60,
            cost=round(meal_cost, 0),
            lat=lunch_lat, lng=lunch_lng, lgu_name=lunch_lgu,
            nearby=nearby_lunch,
        )
        added_lunch = True

    # ── Afternoon snack / merienda between 2:30 PM and 4:30 PM ───────────────
    if 14 * 60 + 30 <= current_mins <= 16 * 60 + 30:
        last_stop = next((s for s in reversed(stops) if s.get("latitude")), None)
        snack_lat = last_stop.get("latitude") if last_stop else None
        snack_lng = last_stop.get("longitude") if last_stop else None
        snack_lgu = last_stop.get("lgu_name", "") if last_stop else ""
        snack_cost = 80 * traveler_count
        if remaining_budget is not None:
            snack_cost = min(snack_cost, remaining_budget * 0.04)
        add_activity(
            "dining", "Merienda / Afternoon Snack",
            "Take a breather! Grab some local snacks — espasol, suman, or fresh buko juice are Laguna favorites.",
            "ph-cookie", duration_mins=30,
            cost=round(snack_cost, 0),
            lat=snack_lat, lng=snack_lng, lgu_name=snack_lgu,
            nearby=_fetch_nearby_places(snack_lat, snack_lng, "dining", 2) if snack_lat else [],
        )

    # ── Dinner: only after 5:30 PM ─────────────────────────────────────────────
    dinner_time = 17 * 60 + 30  # 5:30 PM earliest
    if current_mins < dinner_time:
        # Add free time / leisure until dinner
        free_mins = dinner_time - current_mins
        if free_mins >= 30:
            last_stop = next((s for s in reversed(stops) if s.get("latitude")), None)
            add_activity(
                "leisure", "Free Time & Exploration",
                "Explore the area at your own pace — browse local shops, take photos, or simply relax and soak in the atmosphere.",
                "ph-sun-horizon", duration_mins=free_mins,
                lat=last_stop.get("latitude") if last_stop else None,
                lng=last_stop.get("longitude") if last_stop else None,
                lgu_name=last_stop.get("lgu_name", "") if last_stop else "",
            )
        else:
            current_mins = dinner_time

    last_stop = next((s for s in reversed(stops) if s.get("latitude")), None)
    dinner_lat = last_stop.get("latitude") if last_stop else None
    dinner_lng = last_stop.get("longitude") if last_stop else None
    dinner_lgu = last_stop.get("lgu_name", "") if last_stop else ""
    dinner_cost = meal_budget_per_person * traveler_count * 1.2
    if remaining_budget is not None:
        dinner_cost = min(dinner_cost, remaining_budget * 0.15)
    dinner_cost = max(150 * traveler_count, dinner_cost)
    nearby_dinner = _fetch_nearby_places(dinner_lat, dinner_lng, "dining", 3) if dinner_lat else []
    add_activity(
        "dining", "Dinner",
        "End the day with a satisfying meal. Laguna is known for its fresh lake fish, pancit, and local delicacies.",
        "ph-bowl-food", duration_mins=60,
        cost=round(dinner_cost, 0),
        lat=dinner_lat, lng=dinner_lng, lgu_name=dinner_lgu,
        nearby=nearby_dinner,
    )
    added_dinner = True

    # ── Accommodation (multi-day trips, not last day) ─────────────────────────
    if not is_last_day:
        last_stop = next((s for s in reversed(stops) if s.get("latitude")), None)
        hotel_lat = last_stop.get("latitude") if last_stop else None
        hotel_lng = last_stop.get("longitude") if last_stop else None
        hotel_lgu = last_stop.get("lgu_name", "") if last_stop else ""
        hotel_cost = accommodation_budget
        if remaining_budget is not None:
            hotel_cost = min(hotel_cost, remaining_budget * 0.35)
            hotel_cost = max(500, hotel_cost)
        nearby_hotels = _fetch_nearby_places(hotel_lat, hotel_lng, "accommodation", 3) if hotel_lat else []
        add_activity(
            "accommodation", "Check-in & Rest",
            f"Time to rest and recharge for tomorrow! Find a comfortable place to stay near {hotel_lgu or 'Laguna'}.",
            "ph-bed", duration_mins=0,
            cost=round(hotel_cost, 0),
            lat=hotel_lat, lng=hotel_lng, lgu_name=hotel_lgu,
            nearby=nearby_hotels,
        )

    # ── Wrap-up on last day ───────────────────────────────────────────────────
    if is_last_day:
        add_activity(
            "travel", "Head Home",
            "Safe travels! Don't forget to pick up pasalubong (local souvenirs) before you leave Laguna.",
            "ph-house", duration_mins=0,
        )

    return stops, day_cost


def generate_plan(
    *,
    title: str,
    spots: list[dict[str, Any]],
    start_date: date,
    end_date: date,
    starting_point: str = "",
    starting_lat: float | None = None,
    starting_lng: float | None = None,
    departure_time: str = "08:00",
    return_time: str = "18:00",
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
        return {"ok": False, "error": "Select at least one tourist spot to build your itinerary."}
    if duration_days < 1:
        return {"ok": False, "error": "End date must be on or after the start date."}

    # ── Route spots optimally ──────────────────────────────────────────────────
    coords_list: list[tuple[float, float]] = []
    if starting_lat is not None and starting_lng is not None:
        coords_list.append((starting_lat, starting_lng))
    for spot in spots:
        c = _spot_coords(spot)
        if c:
            coords_list.append(c)

    matrix: list[list[int]] = []
    if len(coords_list) >= 2:
        matrix = travel_matrix_minutes(coords_list)

    offset = 1 if (starting_lat is not None and starting_lng is not None) else 0
    valid_spots = [s for s in spots if _spot_coords(s)]
    no_coord_spots = [s for s in spots if not _spot_coords(s)]

    if route_style == "scenic":
        routed = _order_spots_scenic(valid_spots)
    elif len(valid_spots) > 1 and matrix:
        if offset == 1:
            dummy = {"id": "START", "name": "Start", "latitude": starting_lat, "longitude": starting_lng}
            all_for_routing = [dummy] + valid_spots
            sub_matrix = travel_matrix_minutes([_spot_coords(s) for s in all_for_routing if _spot_coords(s)])
            ordered_with_start = _order_spots_nearest_neighbor(all_for_routing, sub_matrix)
            routed = [s for s in ordered_with_start if s.get("id") != "START"]
        else:
            sub_matrix = travel_matrix_minutes([_spot_coords(s) for s in valid_spots])
            routed = _order_spots_nearest_neighbor(valid_spots, sub_matrix)
    else:
        routed = valid_spots

    routed = routed + no_coord_spots

    # ── Distribute spots across days ──────────────────────────────────────────
    # Spread spots as evenly as possible. If fewer spots than days, some days get 0 spots
    # but still get a full activity timeline (leisure, meals, exploration).
    per_day_max = MAX_SPOTS_PER_DAY.get(pace, 3)
    day_buckets: list[list[dict[str, Any]]] = [[] for _ in trip_days]

    if len(routed) <= duration_days:
        # One spot per day (or less), spread them out
        for i, spot in enumerate(routed):
            day_buckets[i % duration_days].append(spot)
    else:
        # Distribute evenly, capping at per_day_max
        for idx, spot in enumerate(routed):
            day_idx = idx % duration_days
            if len(day_buckets[day_idx]) < per_day_max:
                day_buckets[day_idx].append(spot)
            else:
                # Find a day with room
                for d in range(duration_days):
                    if len(day_buckets[d]) < per_day_max:
                        day_buckets[d].append(spot)
                        break

    # ── Budget allocation ──────────────────────────────────────────────────────
    # Estimate fixed costs first (entrance fees), then allocate remaining to meals/hotel
    total_entrance = sum(
        parse_entrance_fee_estimate(s.get("entrance_fees")) * traveler_count
        for s in routed
    )
    remaining_for_meals = None
    meal_budget_per_person = MEAL_BUDGET_PER_PERSON
    accommodation_budget = ACCOMMODATION_BUDGET_DEFAULT

    if total_budget is not None and total_budget > 0:
        remaining_for_meals = max(0.0, total_budget - total_entrance)
        # Meals: 3 meals/day * duration_days
        total_meal_slots = duration_days * 3
        if total_meal_slots > 0:
            meal_budget_per_person = min(
                MEAL_BUDGET_PER_PERSON,
                (remaining_for_meals * 0.5) / (total_meal_slots * max(1, traveler_count))
            )
            meal_budget_per_person = max(80, meal_budget_per_person)
        # Accommodation: remaining after meals
        nights = max(0, duration_days - 1)
        if nights > 0:
            accommodation_budget = min(
                ACCOMMODATION_BUDGET_DEFAULT,
                (remaining_for_meals * 0.4) / nights
            )
            accommodation_budget = max(300, accommodation_budget)

    # ── Weather ────────────────────────────────────────────────────────────────
    center = _spot_coords(routed[0]) if routed else None
    weather = fetch_weather_forecast(
        lat=center[0] if center else None,
        lon=center[1] if center else None,
        start=start_date,
        end=end_date,
    )

    coord_spots = [s for s in routed if _spot_coords(s)]
    total_estimated = 0.0
    days_out: list[dict[str, Any]] = []

    for day_num, (activity_date, day_spots) in enumerate(zip(trip_days, day_buckets), start=1):
        day_key = activity_date.isoformat()
        forecast = weather.get("daily", {}).get(day_key)
        is_last = (day_num == duration_days)

        stops, day_cost = _build_full_day_timeline(
            day_num=day_num,
            activity_date=activity_date,
            day_spots=day_spots,
            departure_time=departure_time,
            return_time=return_time,
            traveler_count=traveler_count,
            pace=pace,
            duration_days=duration_days,
            is_last_day=is_last,
            coord_spots=coord_spots,
            matrix=matrix,
            spot_priorities=spot_priorities,
            remaining_budget=remaining_for_meals,
            meal_budget_per_person=meal_budget_per_person,
            accommodation_budget=accommodation_budget,
            forecast=forecast,
        )
        total_estimated += day_cost

        days_out.append({
            "day_number": day_num,
            "activity_date": day_key,
            "label": activity_date.strftime("%A, %b %d"),
            "weather": forecast,
            "clothing_tip": clothing_tip(forecast),
            "stops": stops,
        })

    budget_remaining = None
    if total_budget is not None and total_budget > 0:
        budget_remaining = round(total_budget - total_estimated, 2)

    summary = (
        f"Trip: {title}; {duration_days} days; {len(routed)} spots; "
        f"purpose={trip_purpose}; travelers={traveler_count}; budget={'₱'+str(total_budget) if total_budget else 'open'}; "
        f"starting={starting_point or 'Laguna'}."
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
            {"name": "Beep Card / stored-value", "detail": "Useful if your route includes Metro Manila connections to Laguna."},
            {"name": "Jeepney & tricycle cash", "detail": "Have small bills for short hops between spots within municipalities."},
        ],
    }
