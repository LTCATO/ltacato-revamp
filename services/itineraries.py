"""
Saved itineraries and planner spot catalog.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services.supabase_client import get_supabase

PLANNER_SPOT_FIELDS = (
    "id, name, description, hook_title, hook_text, address, main_image_url, "
    "entrance_fees, opening_hours, best_time_to_visit, food_options, parking_info, "
    "latitude, longitude, rating, reviews_count, lgu_id, category_id, "
    "attraction_categories(id, name), lgus(id, name)"
)

ITINERARY_FIELDS = (
    "id, title, total_budget, estimated_expense, start_date, end_date, notes, "
    "trip_purpose, starting_point, starting_lat, starting_lng, traveler_count, "
    "preferences, created_at"
)

ITEM_FIELDS = (
    "id, itinerary_id, tourist_spot_id, day_number, activity_date, activity_time, "
    "notes, estimated_cost, accommodation, transportation, priority, time_slot, "
    "sort_order, travel_minutes, "
    "tourist_spots(id, name, main_image_url, address, latitude, longitude, "
    "entrance_fees, opening_hours, rating, lgus(id, name))"
)


def list_planner_spots(
    *,
    q: str | None = None,
    category_id: int | None = None,
    lgu_id: int | None = None,
    limit: int = 150,
) -> list[dict[str, Any]]:
    query = (
        get_supabase()
        .table("tourist_spots")
        .select(PLANNER_SPOT_FIELDS)
        .neq("approval_status", "rejected")
    )
    if category_id:
        query = query.eq("category_id", category_id)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    if q:
        term = q.strip()
        if term:
            query = query.or_(
                f"name.ilike.%{term}%,description.ilike.%{term}%,address.ilike.%{term}%"
            )
    response = query.order("name").limit(limit).execute()
    return response.data or []


def get_spots_by_ids(spot_ids: list[int]) -> list[dict[str, Any]]:
    if not spot_ids:
        return []
    response = (
        get_supabase()
        .table("tourist_spots")
        .select(PLANNER_SPOT_FIELDS)
        .eq("approval_status", "approved")
        .in_("id", spot_ids)
        .execute()
    )
    rows = response.data or []
    order = {sid: i for i, sid in enumerate(spot_ids)}
    return sorted(rows, key=lambda r: order.get(r["id"], 999))


def list_user_itineraries(tourist_id: str, limit: int = 50) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("itineraries")
        .select(ITINERARY_FIELDS)
        .eq("tourist_id", tourist_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_itinerary(itinerary_id: int, tourist_id: str) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("itineraries")
            .select(ITINERARY_FIELDS)
            .eq("id", itinerary_id)
            .eq("tourist_id", tourist_id)
            .single()
            .execute()
        )
        itinerary = response.data
    except Exception:
        return None

    if not itinerary:
        return None

    items_resp = (
        get_supabase()
        .table("itinerary_items")
        .select(ITEM_FIELDS)
        .eq("itinerary_id", itinerary_id)
        .order("day_number")
        .order("sort_order")
        .order("activity_time")
        .execute()
    )
    itinerary["items"] = items_resp.data or []
    return itinerary


def itinerary_item_count(itinerary_id: int) -> int:
    response = (
        get_supabase()
        .table("itinerary_items")
        .select("id", count="exact")
        .eq("itinerary_id", itinerary_id)
        .execute()
    )
    return response.count or 0


def save_itinerary_from_plan(
    tourist_id: str,
    plan: dict[str, Any],
    *,
    itinerary_id: int | None = None,
) -> tuple[bool, int | None, str | None]:
    if not plan.get("ok"):
        return False, None, plan.get("error") or "Invalid plan."

    # Dining/accommodation/free-day/return stops are generated suggestions,
    # not real tourist_spot visits — they have no tourist_spot_id, so they
    # don't fit itinerary_items (which is keyed around a real spot). They're
    # kept here instead, so a reloaded saved itinerary can still show them
    # (with working nearby-restaurant/hotel lookups) rather than showing up
    # as blank "None" spot cards once the tourist_spot join comes back empty.
    suggestion_stops = [
        {
            "day_number": day.get("day_number"),
            "type": stop.get("type"),
            "name": stop.get("name"),
            "description": stop.get("description"),
            "lgu_name": stop.get("lgu_name"),
            "activity_date": stop.get("activity_date"),
            "activity_time": stop.get("activity_time"),
            "estimated_cost": stop.get("estimated_cost"),
            "notes": stop.get("notes"),
            "travel_minutes": stop.get("travel_minutes"),
            "search_lat": stop.get("search_lat"),
            "search_lng": stop.get("search_lng"),
        }
        for day in plan.get("days") or []
        for stop in day.get("stops") or []
        if not stop.get("tourist_spot_id")
    ]

    preferences = {
        "pace": plan.get("pace"),
        "route_style": plan.get("route_style"),
        "category_ids": plan.get("category_ids") or [],
        "weather": plan.get("weather"),
        "smart_tips": plan.get("smart_tips"),
        "transport_cards": plan.get("transport_cards"),
        "emergency": plan.get("emergency"),
        "timezone": plan.get("timezone"),
        "currency": plan.get("currency"),
        "suggestion_stops": suggestion_stops,
    }

    payload = {
        "tourist_id": tourist_id,
        "title": (plan.get("title") or "My Laguna Trip").strip()[:200],
        "total_budget": plan.get("total_budget"),
        "estimated_expense": plan.get("estimated_expense"),
        "start_date": plan.get("start_date"),
        "end_date": plan.get("end_date"),
        "notes": plan.get("notes") or None,
        "trip_purpose": plan.get("trip_purpose") or "vacation",
        "starting_point": plan.get("starting_point") or None,
        "starting_lat": plan.get("starting_lat"),
        "starting_lng": plan.get("starting_lng"),
        "traveler_count": max(1, int(plan.get("traveler_count") or 1)),
        "preferences": preferences,
    }

    try:
        if itinerary_id:
            get_supabase().table("itineraries").update(payload).eq(
                "id", itinerary_id
            ).eq("tourist_id", tourist_id).execute()
            get_supabase().table("itinerary_items").delete().eq(
                "itinerary_id", itinerary_id
            ).execute()
            saved_id = itinerary_id
        else:
            ins = get_supabase().table("itineraries").insert(payload).execute()
            saved_id = (ins.data or [{}])[0].get("id")
            if not saved_id:
                return False, None, "Could not save itinerary."

        items: list[dict[str, Any]] = []
        sort_order = 0
        for day in plan.get("days") or []:
            for stop in day.get("stops") or []:
                sort_order += 1
                if not stop.get("tourist_spot_id"):
                    # Suggestion stop (dining/accommodation/free_day/return) —
                    # saved above in preferences.suggestion_stops instead.
                    continue
                items.append(
                    {
                        "itinerary_id": saved_id,
                        "tourist_spot_id": stop["tourist_spot_id"],
                        "day_number": stop.get("day_number"),
                        "activity_date": stop.get("activity_date"),
                        "activity_time": stop.get("activity_time"),
                        "notes": stop.get("notes"),
                        "estimated_cost": stop.get("estimated_cost"),
                        "transportation": stop.get("transportation"),
                        "priority": stop.get("priority", "must_visit"),
                        "time_slot": stop.get("time_slot"),
                        "sort_order": sort_order,
                        "travel_minutes": stop.get("travel_minutes") or 0,
                    }
                )

        if items:
            get_supabase().table("itinerary_items").insert(items).execute()

        return True, int(saved_id), None
    except Exception:
        return False, None, "Unable to save your itinerary. Please try again."


def delete_itinerary(itinerary_id: int, tourist_id: str) -> bool:
    try:
        get_supabase().table("itinerary_items").delete().eq(
            "itinerary_id", itinerary_id
        ).execute()
        get_supabase().table("itineraries").delete().eq("id", itinerary_id).eq(
            "tourist_id", tourist_id
        ).execute()
        return True
    except Exception:
        return False


def plan_from_itinerary_row(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct a display plan from a saved itinerary."""
    items = row.get("items") or []
    by_day: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        day_num = item.get("day_number") or 1
        by_day.setdefault(day_num, []).append(item)

    prefs = row.get("preferences") or {}
    weather = prefs.get("weather") or {}

    # Dining/accommodation/free-day/return suggestions live in preferences
    # (see save_itinerary_from_plan), not itinerary_items — merge them back
    # in per day, chronologically, same as a freshly generated plan.
    suggestions_by_day: dict[int, list[dict[str, Any]]] = {}
    for sugg in prefs.get("suggestion_stops") or []:
        day_num = sugg.get("day_number") or 1
        suggestions_by_day.setdefault(day_num, []).append(sugg)

    days_out: list[dict[str, Any]] = []
    for day_num in sorted(set(by_day) | set(suggestions_by_day)):
        raw_stops = by_day.get(day_num, [])
        stops = []
        for item in raw_stops:
            spot = item.get("tourist_spots") or {}
            lgu = spot.get("lgus") or {}
            stops.append(
                {
                    "tourist_spot_id": item.get("tourist_spot_id"),
                    "type": "spot",
                    "name": spot.get("name"),
                    "main_image_url": spot.get("main_image_url"),
                    "address": spot.get("address"),
                    "latitude": spot.get("latitude"),
                    "longitude": spot.get("longitude"),
                    "entrance_fees": spot.get("entrance_fees"),
                    "opening_hours": spot.get("opening_hours"),
                    "rating": spot.get("rating"),
                    "lgu_name": lgu.get("name") if isinstance(lgu, dict) else "Laguna",
                    "day_number": day_num,
                    "activity_date": item.get("activity_date"),
                    "activity_time": str(item.get("activity_time") or "")[:5],
                    "time_slot": item.get("time_slot"),
                    "priority": item.get("priority"),
                    "estimated_cost": item.get("estimated_cost"),
                    "travel_minutes": item.get("travel_minutes"),
                    "transportation": item.get("transportation"),
                    "notes": item.get("notes"),
                }
            )
        for sugg in suggestions_by_day.get(day_num, []):
            stops.append(
                {
                    "tourist_spot_id": None,
                    "type": sugg.get("type"),
                    "name": sugg.get("name"),
                    "description": sugg.get("description"),
                    "lgu_name": sugg.get("lgu_name"),
                    "day_number": day_num,
                    "activity_date": sugg.get("activity_date"),
                    "activity_time": str(sugg.get("activity_time") or "")[:5],
                    "estimated_cost": sugg.get("estimated_cost"),
                    "notes": sugg.get("notes"),
                    "travel_minutes": sugg.get("travel_minutes"),
                    "search_lat": sugg.get("search_lat"),
                    "search_lng": sugg.get("search_lng"),
                }
            )
        stops.sort(key=lambda s: s.get("activity_time") or "00:00")

        act_date = raw_stops[0].get("activity_date") if raw_stops else None
        if not act_date and suggestions_by_day.get(day_num):
            act_date = suggestions_by_day[day_num][0].get("activity_date")
        act_date = act_date or ""
        day_key = str(act_date)[:10] if act_date else ""
        forecast = (weather.get("daily") or {}).get(day_key)
        label = day_key
        try:
            label = date.fromisoformat(day_key).strftime("%A, %b %d")
        except ValueError:
            pass
        days_out.append(
            {
                "day_number": day_num,
                "activity_date": day_key,
                "label": label,
                "weather": forecast,
                "stops": stops,
            }
        )

    return {
        "ok": True,
        "title": row.get("title"),
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
        "duration_days": len(days_out),
        "starting_point": row.get("starting_point"),
        "starting_lat": row.get("starting_lat"),
        "starting_lng": row.get("starting_lng"),
        "traveler_count": row.get("traveler_count"),
        "trip_purpose": row.get("trip_purpose"),
        "total_budget": row.get("total_budget"),
        "estimated_expense": row.get("estimated_expense"),
        "notes": row.get("notes"),
        "days": days_out,
        "weather": weather,
        "smart_tips": prefs.get("smart_tips") or [],
        "transport_cards": prefs.get("transport_cards") or [],
        "emergency": prefs.get("emergency") or {},
        "timezone": prefs.get("timezone") or "Asia/Manila",
        "currency": prefs.get("currency") or "PHP",
        "saved": True,
        "itinerary_id": row.get("id"),
    }
