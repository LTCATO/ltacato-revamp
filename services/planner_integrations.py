"""
External APIs for itinerary planning: Google Distance Matrix and OpenWeather.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

# Laguna provincial center (Santa Cruz area) for default weather
LAGUNA_CENTER = (14.2691, 121.4119)

SLOT_TIMES = {
    "morning": "09:00",
    "afternoon": "13:30",
    "evening": "17:00",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_travel_minutes(distance_km: float) -> int:
    """Rough drive time in Laguna traffic."""
    if distance_km <= 0:
        return 0
    speed_kmh = 28.0
    return max(5, int((distance_km / speed_kmh) * 60))


def _http_get_json(url: str, timeout: int = 12) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LTCATO-Planner/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return None


def travel_matrix_minutes(
    points: list[tuple[float, float]],
) -> list[list[int]]:
    """
    Return NxN matrix of travel minutes between points.
    Falls back to haversine estimates when Maps API is unavailable.
    """
    n = len(points)
    if n == 0:
        return []
    if n == 1:
        return [[0]]

    api_key = (os.getenv("MAP_API_KEY") or "").strip()
    matrix: list[list[int]] = [[0] * n for _ in range(n)]

    if api_key:
        origins = "|".join(f"{lat},{lng}" for lat, lng in points)
        destinations = origins
        params = urllib.parse.urlencode(
            {
                "origins": origins,
                "destinations": destinations,
                "mode": "driving",
                "region": "ph",
                "key": api_key,
            }
        )
        url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{params}"
        data = _http_get_json(url)
        if data and data.get("status") == "OK":
            rows = data.get("rows") or []
            for i, row in enumerate(rows):
                elements = row.get("elements") or []
                for j, el in enumerate(elements):
                    if el.get("status") == "OK":
                        sec = (el.get("duration") or {}).get("value")
                        if sec is not None:
                            matrix[i][j] = max(1, int(sec) // 60)
                            continue
                    if i != j:
                        km = haversine_km(*points[i], *points[j])
                        matrix[i][j] = estimate_travel_minutes(km)
            return matrix

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            km = haversine_km(*points[i], *points[j])
            matrix[i][j] = estimate_travel_minutes(km)
    return matrix


def fetch_weather_forecast(
    *,
    lat: float | None = None,
    lon: float | None = None,
    start: date | None = None,
    end: date | None = None,
) -> dict[str, Any]:
    """Daily-ish forecast summary keyed by ISO date string."""
    api_key = (os.getenv("WEATHER_API_KEY") or "").strip()
    lat = lat if lat is not None else LAGUNA_CENTER[0]
    lon = lon if lon is not None else LAGUNA_CENTER[1]

    result: dict[str, Any] = {
        "location": "Laguna, Philippines",
        "timezone": "Asia/Manila",
        "currency": "PHP",
        "daily": {},
        "alerts": [],
    }

    if not api_key:
        result["alerts"].append("Weather API key not configured — forecasts unavailable.")
        return result

    params = urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "appid": api_key, "units": "metric", "cnt": 40}
    )
    url = f"https://api.openweathermap.org/data/2.5/forecast?{params}"
    data = _http_get_json(url)
    if not data or data.get("cod") != "200":
        result["alerts"].append("Unable to load weather forecast right now.")
        return result

    city = (data.get("city") or {}).get("name")
    if city:
        result["location"] = f"{city}, Philippines"

    by_day: dict[str, list[dict[str, Any]]] = {}
    for item in data.get("list") or []:
        dt_txt = item.get("dt_txt") or ""
        day_key = dt_txt[:10]
        if not day_key:
            continue
        main = item.get("main") or {}
        weather = (item.get("weather") or [{}])[0]
        by_day.setdefault(day_key, []).append(
            {
                "temp": main.get("temp"),
                "feels_like": main.get("feels_like"),
                "humidity": main.get("humidity"),
                "description": weather.get("description"),
                "icon": weather.get("icon"),
                "pop": (item.get("pop") or 0) * 100,
            }
        )

    for day_key, entries in by_day.items():
        temps = [e["temp"] for e in entries if e.get("temp") is not None]
        pops = [e["pop"] for e in entries if e.get("pop") is not None]
        desc = max(entries, key=lambda e: e.get("pop") or 0)
        result["daily"][day_key] = {
            "temp_min": round(min(temps), 1) if temps else None,
            "temp_max": round(max(temps), 1) if temps else None,
            "description": desc.get("description"),
            "icon": desc.get("icon"),
            "rain_chance": round(max(pops), 0) if pops else 0,
        }

    if start and end:
        filtered = {}
        d = start
        while d <= end:
            key = d.isoformat()
            if key in result["daily"]:
                filtered[key] = result["daily"][key]
            d += timedelta(days=1)
        result["daily"] = filtered

        for key, day in filtered.items():
            if (day.get("rain_chance") or 0) >= 60:
                result["alerts"].append(
                    f"Rain likely on {key} — consider indoor alternatives for outdoor spots."
                )

    return result


def parse_entrance_fee_estimate(text: str | None) -> float:
    """Best-effort PHP estimate from free-text entrance fee field."""
    if not text:
        return 0.0
    lowered = text.lower()
    if "free" in lowered and "except" not in lowered:
        return 0.0
    import re

    numbers = [float(x.replace(",", "")) for x in re.findall(r"(\d+(?:\.\d+)?)", text)]
    if not numbers:
        return 150.0
    return float(min(numbers))


def clothing_tip(forecast_day: dict[str, Any] | None) -> str:
    if not forecast_day:
        return "Light, breathable clothing and comfortable walking shoes."
    tmax = forecast_day.get("temp_max") or 30
    rain = forecast_day.get("rain_chance") or 0
    tips = []
    if tmax >= 32:
        tips.append("sunscreen and a hat")
    if rain >= 50:
        tips.append("a compact umbrella or rain jacket")
    if tmax <= 24:
        tips.append("a light jacket for cooler hours")
    if not tips:
        return "Light cotton clothing and comfortable shoes."
    return "Bring " + ", ".join(tips) + "."
