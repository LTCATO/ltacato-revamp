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


def _order_spots_compact(spots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group spots by LGU (town) so the route stays within fewer municipalities,
    ordering towns and in-town stops by travel proximity."""
    by_lgu: dict[int | str, list[dict[str, Any]]] = {}
    for spot in spots:
        key = spot.get("lgu_id") or "unknown"
        by_lgu.setdefault(key, []).append(spot)
    groups = list(by_lgu.values())

    def _centroid(group: list[dict[str, Any]]) -> tuple[float, float] | None:
        coords = [c for c in (_spot_coords(s) for s in group) if c]
        if not coords:
            return None
        return (
            sum(c[0] for c in coords) / len(coords),
            sum(c[1] for c in coords) / len(coords),
        )

    centroids = [_centroid(g) for g in groups]
    coord_town_idx = [i for i, c in enumerate(centroids) if c]
    town_order = list(range(len(groups)))

    if len(coord_town_idx) >= 2:
        town_matrix = travel_matrix_minutes([centroids[i] for i in coord_town_idx])
        remaining = set(range(len(coord_town_idx)))
        order = [0]
        remaining.remove(0)
        current = 0
        while remaining:
            nxt = min(remaining, key=lambda j: town_matrix[current][j])
            order.append(nxt)
            remaining.remove(nxt)
            current = nxt
        no_coord_towns = [i for i in town_order if i not in coord_town_idx]
        town_order = [coord_town_idx[i] for i in order] + no_coord_towns

    ordered: list[dict[str, Any]] = []
    for ti in town_order:
        group = groups[ti]
        coord_group = [s for s in group if _spot_coords(s)]
        no_coord_group = [s for s in group if not _spot_coords(s)]
        if len(coord_group) >= 2:
            group_matrix = travel_matrix_minutes([_spot_coords(s) for s in coord_group])
            ordered.extend(_order_spots_nearest_neighbor(coord_group, group_matrix))
            ordered.extend(no_coord_group)
        else:
            ordered.extend(group)
    return ordered


def _trip_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def _dining_suggestion(
    coords: tuple[float, float] | None,
    day_key: str,
    time_str: str,
    lgu_name: str,
    traveler_count: int,
) -> dict[str, Any]:
    # Real nearby places are looked up client-side (see /planner/nearby-places)
    # rather than during generation: Overpass is a free, sometimes-slow public
    # service, and a synchronous call here would either stall plan generation
    # or — worse — freeze a failed lookup into a saved itinerary forever.
    return {
        "tourist_spot_id": None,
        "type": "dining",
        "name": "Local Dining Suggestion",
        "description": f"Take a break and enjoy some local Laguna cuisine near {lgu_name or 'your current location'}.",
        "lgu_name": lgu_name,
        "activity_date": day_key,
        "activity_time": time_str,
        "estimated_cost": 300 * max(1, traveler_count),
        "notes": "Try finding a local eatery or ask locals for the best buko pie or special dishes.",
        "search_lat": coords[0] if coords else None,
        "search_lng": coords[1] if coords else None,
    }


def _accommodation_suggestion(
    coords: tuple[float, float] | None,
    day_key: str,
    lgu_name: str,
    return_time: str,
) -> dict[str, Any]:
    return {
        "tourist_spot_id": None,
        "type": "accommodation",
        "name": "Accommodation / Rest",
        "description": f"Time to rest and recharge for tomorrow! We recommend finding a place to stay near {lgu_name or 'Laguna'}.",
        "lgu_name": lgu_name,
        "activity_date": day_key,
        "activity_time": return_time,
        "estimated_cost": 2000,
        "notes": "Consider booking a local resort, inn, or homestay to experience Laguna hospitality.",
        "search_lat": coords[0] if coords else None,
        "search_lng": coords[1] if coords else None,
    }


def _gemini_tips(plan_summary: str) -> list[str]:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"')
    if not api_key:
        return []

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
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
        return {
            "ok": False,
            "error": "Select at least one tourist spot to build your itinerary.",
        }

    if not starting_point.strip():
        return {
            "ok": False,
            "error": "Enter your starting point so we can plan travel time and directions.",
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
    # Maps a spot's id to its column/row index in `coords_list`/`matrix`, built in
    # lockstep with `coords_list` so it stays valid regardless of how `routed`
    # later reorders spots (or how many coordless spots sit in between). "START"
    # maps to the traveler's starting point when one was given, so travel time
    # to the first stop and back at the end can reuse the same matrix.
    spot_matrix_index: dict[Any, int] = {}
    has_start = starting_lat is not None and starting_lng is not None

    # If starting coordinates are provided, consider it the first coordinate for routing
    if has_start:
        spot_matrix_index["START"] = len(coords_list)
        coords_list.append((starting_lat, starting_lng))

    for spot in ordered_pool:
        c = _spot_coords(spot)
        if c:
            spot_matrix_index[spot["id"]] = len(coords_list)
            coords_list.append(c)
            valid_spots.append(spot)
        else:
            valid_spots.append(spot)

    matrix: list[list[int]] = []
    if len(coords_list) >= 2:
        matrix = travel_matrix_minutes(coords_list)

        if route_style == "scenic":
            routed = _order_spots_scenic(valid_spots)
        elif route_style == "compact":
            routed = _order_spots_compact(valid_spots)
        else:
            sub_spots = [s for s in valid_spots if _spot_coords(s)]
            if sub_spots:
                # To properly route from the starting point, include it as a dummy
                # spot so `_order_spots_nearest_neighbor` (which starts at index 0)
                # naturally begins there.
                if has_start:
                    dummy_spot = {"id": "START", "name": "Start", "latitude": starting_lat, "longitude": starting_lng}
                    spots_for_routing = [dummy_spot] + sub_spots
                    sub_matrix = travel_matrix_minutes([_spot_coords(s) for s in spots_for_routing])
                    sub_ordered_with_start = _order_spots_nearest_neighbor(spots_for_routing, sub_matrix)
                    sub_ordered = [s for s in sub_ordered_with_start if s.get("id") != "START"]
                else:
                    sub_matrix = travel_matrix_minutes([_spot_coords(s) for s in sub_spots])
                    sub_ordered = _order_spots_nearest_neighbor(sub_spots, sub_matrix)

                no_coord = [s for s in valid_spots if not _spot_coords(s)]
                routed = sub_ordered + no_coord
            else:
                routed = valid_spots
    else:
        if route_style == "scenic":
            routed = _order_spots_scenic(valid_spots)
        elif route_style == "compact":
            routed = _order_spots_compact(valid_spots)
        else:
            routed = valid_spots

    # Spots are pulled onto each day from this shared queue (in route order) as
    # the day's time budget allows, rather than being pre-chunked by count —
    # see the days loop below.
    per_day = MAX_SPOTS_PER_DAY.get(pace, 3)

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

    # Seeding with the starting point (when given) means the first real stop of
    # the trip gets a genuine travel-time-from-start instead of 0, and the last
    # day can compute a travel-time-back below.
    prev_spot_with_coords: dict[str, Any] | None = (
        {"id": "START", "latitude": starting_lat, "longitude": starting_lng} if has_start else None
    )
    last_known_lgu_name = ""
    routed_queue = list(routed)
    queue_idx = 0
    empty_days = 0

    for day_num, activity_date in enumerate(trip_days, start=1):
        day_key = activity_date.isoformat()
        forecast = weather.get("daily", {}).get(day_key)
        stops: list[dict[str, Any]] = []
        is_last_day = day_num == duration_days

        try:
            dh, dm = map(int, departure_time.split(":"))
        except ValueError:
            dh, dm = 8, 0
        current_time_mins = dh * 60 + dm

        try:
            rh, rm = map(int, return_time.split(":"))
            return_time_mins = rh * 60 + rm
        except ValueError:
            return_time_mins = current_time_mins + 10 * 60
        if return_time_mins <= current_time_mins:
            return_time_mins = current_time_mins + 10 * 60

        added_lunch = False
        day_stop_count = 0

        # Spread remaining spots evenly across remaining days (still bounded by
        # the pace cap) instead of always filling today to the pace cap first —
        # otherwise a handful of spots front-load onto day 1 and leave later
        # days empty.
        remaining_days = duration_days - day_num + 1
        remaining_spots = len(routed_queue) - queue_idx
        day_cap = min(per_day, -(-remaining_spots // remaining_days))

        while queue_idx < len(routed_queue) and (day_stop_count < day_cap or is_last_day):
            spot = routed_queue[queue_idx]

            travel_minutes = 0
            c = _spot_coords(spot)
            if c and prev_spot_with_coords is not None and matrix:
                prev_idx = spot_matrix_index.get(prev_spot_with_coords["id"])
                cur_idx = spot_matrix_index.get(spot["id"])
                if prev_idx is not None and cur_idx is not None:
                    try:
                        travel_minutes = matrix[prev_idx][cur_idx]
                    except IndexError:
                        travel_minutes = 0

            arrival = current_time_mins + travel_minutes

            # Stop pulling more spots into today once travel + visit time would
            # run past the traveler's return time — leave the rest for the next
            # day instead of silently overbooking. Always allow at least one
            # stop so a day is never left empty, and never hold spots back on
            # the last day so nothing selected gets dropped from the plan.
            if day_stop_count > 0 and not is_last_day and arrival + 120 > return_time_mins:
                break

            # Inject lunch if time crosses noon or it's the second stop
            if not added_lunch and arrival >= 11 * 60 + 30:
                lunch_time_str = f"{arrival // 60:02d}:{arrival % 60:02d}"
                lunch_coords = _spot_coords(prev_spot_with_coords) if prev_spot_with_coords else center
                stops.append(
                    _dining_suggestion(
                        lunch_coords,
                        day_key,
                        lunch_time_str,
                        last_known_lgu_name,
                        traveler_count,
                    )
                )
                total_estimated += 300 * max(1, traveler_count)
                arrival += 90 # 1.5 hours for lunch
                added_lunch = True

            current_time_mins = arrival

            time_slot = slots[slot_idx % len(slots)]
            slot_idx += 1
            priority = spot_priorities.get(spot["id"], "must_visit")
            fee = parse_entrance_fee_estimate(spot.get("entrance_fees"))
            cost = fee * max(1, traveler_count)
            total_estimated += cost

            if c:
                prev_spot_with_coords = spot

            lgu = spot.get("lgus") or {}
            cat = spot.get("attraction_categories") or {}
            if isinstance(lgu, dict) and lgu.get("name"):
                last_known_lgu_name = lgu["name"]

            activity_time_str = f"{current_time_mins // 60:02d}:{current_time_mins % 60:02d}"

            stops.append(
                {
                    "tourist_spot_id": spot["id"],
                    "type": "spot",
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
                    "activity_time": activity_time_str,
                    "time_slot": time_slot,
                    "priority": priority,
                    "estimated_cost": cost,
                    "travel_minutes": travel_minutes,
                    "transportation": "Private car / ride-hail recommended between stops",
                    "notes": "",
                }
            )

            current_time_mins += 120 # visit duration; travel to the next spot is added next iteration
            queue_idx += 1
            day_stop_count += 1

        if day_stop_count == 0:
            # Nothing landed on this day (fewer selected spots than the trip is
            # long) — say so plainly instead of showing a lunch/hotel stub with
            # no real anchor, which reads like a bug rather than a free day.
            empty_days += 1
            stops.append(
                {
                    "tourist_spot_id": None,
                    "type": "free_day",
                    "name": "Free day",
                    "description": "No spots scheduled today — add more spots to your plan, or use this day to "
                    "revisit a favorite, rest, or explore Laguna at your own pace.",
                    "lgu_name": last_known_lgu_name,
                    "activity_date": day_key,
                    "activity_time": f"{current_time_mins // 60:02d}:{current_time_mins % 60:02d}",
                    "estimated_cost": 0,
                    "notes": "",
                }
            )
        elif not added_lunch and current_time_mins < 15 * 60:
            # Ensure lunch is added even if few stops
            lunch_time_str = "12:30"
            lunch_coords = _spot_coords(prev_spot_with_coords) if prev_spot_with_coords else center
            stops.append(
                _dining_suggestion(
                    lunch_coords,
                    day_key,
                    lunch_time_str,
                    last_known_lgu_name,
                    traveler_count,
                )
            )
            total_estimated += 300 * max(1, traveler_count)

        if duration_days >= 2 and day_num < duration_days:
            stay_coords = _spot_coords(prev_spot_with_coords) if prev_spot_with_coords else center
            stops.append(
                _accommodation_suggestion(
                    stay_coords,
                    day_key,
                    last_known_lgu_name or "Laguna",
                    return_time,
                )
            )
            total_estimated += 2000
        elif is_last_day and has_start:
            # Close the loop: estimate the drive back to the traveler's starting
            # point using the same matrix built for the outbound leg, instead of
            # just ending the plan at the last spot with no way home.
            travel_back_minutes = 0
            if prev_spot_with_coords is not None and matrix:
                prev_idx = spot_matrix_index.get(prev_spot_with_coords["id"])
                start_idx = spot_matrix_index.get("START")
                if prev_idx is not None and start_idx is not None:
                    try:
                        travel_back_minutes = matrix[prev_idx][start_idx]
                    except IndexError:
                        travel_back_minutes = 0
            return_mins = current_time_mins + travel_back_minutes
            stops.append(
                {
                    "tourist_spot_id": None,
                    "type": "return",
                    "name": f"Head back to {starting_point}" if starting_point else "Head back to your starting point",
                    "description": f"Estimated ~{travel_back_minutes} min drive back to "
                    f"{starting_point or 'where you started'}. Safe travels!",
                    "lgu_name": "",
                    "activity_date": day_key,
                    "activity_time": f"{return_mins // 60 % 24:02d}:{return_mins % 60:02d}",
                    "estimated_cost": 0,
                    "travel_minutes": travel_back_minutes,
                    "notes": "",
                }
            )

        # Sort chronologically — dining/accommodation/return entries are appended
        # as they're decided, not necessarily in clock order.
        stops.sort(key=lambda s: s.get("activity_time", "00:00"))

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

    warnings: list[str] = []
    if empty_days:
        warnings.append(
            f"You selected {len(routed)} spot{'s' if len(routed) != 1 else ''} for a {duration_days}-day trip — "
            f"{empty_days} day{'s' if empty_days != 1 else ''} {'have' if empty_days != 1 else 'has'} no scheduled "
            "activities. Add more spots or "
            "shorten the trip for a fuller itinerary."
        )
    if not has_start:
        warnings.append(
            "No starting point was set, so travel times only cover the selected spots — set one next time to see "
            "travel to your first stop and the trip back."
        )

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
        "starting_lat": starting_lat,
        "starting_lng": starting_lng,
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
        "warnings": warnings,
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
