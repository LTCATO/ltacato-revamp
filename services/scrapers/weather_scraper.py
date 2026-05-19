"""Weather scraper — OpenWeatherMap free API. Reads WEATHER_API_KEY from .env."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import requests

from services.supabase_client import get_supabase

OPENWEATHER_API_KEY = os.getenv("WEATHER_API_KEY") or os.getenv(
    "OPENWEATHERMAP_API_KEY"
)
BASE_URL = "https://api.openweathermap.org/data/2.5"


def _get_lgus() -> list[dict]:
    try:
        return (
            get_supabase()
            .table("lgus")
            .select("id, name, latitude, longitude")
            .order("name")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def scrape_weather_for_lgus() -> dict[str, Any]:
    if not OPENWEATHER_API_KEY:
        return {"ok": False, "error": "WEATHER_API_KEY not set in .env.", "inserted": 0}
    lgus = _get_lgus()
    if not lgus:
        return {"ok": False, "error": "No LGUs found in database.", "inserted": 0}
    inserted = 0
    errors: list[str] = []
    for lgu in lgus:
        lat = lgu.get("latitude")
        lon = lgu.get("longitude")
        if not lat or not lon:
            continue
        try:
            resp = requests.get(
                f"{BASE_URL}/weather",
                params={
                    "lat": float(lat),
                    "lon": float(lon),
                    "appid": OPENWEATHER_API_KEY,
                    "units": "metric",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                errors.append(f"{lgu['name']}: HTTP {resp.status_code}")
                continue
            d = resp.json()
            w = d.get("weather", [{}])[0]
            m = d.get("main", {})
            wind = d.get("wind", {})
            get_supabase().table("scraped_weather").insert(
                {
                    "location": lgu["name"],
                    "lgu_id": lgu["id"],
                    "temperature_celsius": m.get("temp"),
                    "feels_like_celsius": m.get("feels_like"),
                    "humidity_percent": m.get("humidity"),
                    "weather_main": w.get("main"),
                    "weather_description": w.get("description"),
                    "wind_speed_mps": wind.get("speed"),
                    "visibility_meters": d.get("visibility"),
                    "is_forecast": False,
                    "forecast_date": date.today().isoformat(),
                    "raw_data": d,
                    "scraped_at": datetime.now(
                        datetime.UTC if hasattr(datetime, "UTC") else None
                    ).isoformat()
                    if False
                    else datetime.utcnow().isoformat(),
                }
            ).execute()
            inserted += 1
        except Exception as exc:
            errors.append(f"{lgu['name']}: {exc}")
    return {"ok": True, "inserted": inserted, "errors": errors}


def get_latest_weather(lgu_id: int | None = None) -> list[dict]:
    try:
        q = (
            get_supabase()
            .table("scraped_weather")
            .select(
                "id,location,lgu_id,temperature_celsius,feels_like_celsius,"
                "humidity_percent,weather_main,weather_description,"
                "wind_speed_mps,visibility_meters,forecast_date,scraped_at"
            )
            .eq("is_forecast", False)
            .order("scraped_at", desc=True)
        )
        if lgu_id:
            q = q.eq("lgu_id", lgu_id)
        rows = q.limit(60).execute().data or []
        seen: set = set()
        unique: list[dict] = []
        for row in rows:
            lid = row.get("lgu_id")
            if lid not in seen:
                seen.add(lid)
                unique.append(row)
        return unique
    except Exception:
        return []


def get_weather_alert(rows: list[dict]) -> str | None:
    bad = {"rain", "storm", "thunderstorm", "typhoon", "drizzle", "squall", "tornado"}
    for row in rows:
        desc = (row.get("weather_description") or "").lower()
        if any(w in desc for w in bad):
            return f"{row.get('location', '?')}: {row.get('weather_description', '')}"
    return None
