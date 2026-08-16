"""
Distance/ETA estimation for LARA — hybrid online + database.

The origin and destination are always resolved from real coordinates
already stored in the database (tourist_spots and lgus both have
latitude/longitude). For the actual distance/time, this tries OSRM
(Open Source Routing Machine, router.project-osrm.org — free, no API key,
no billing) first for a real road route, and falls back to a straight-line
(haversine) estimate with a fixed road-curvature factor and average speed
whenever that's unreachable or returns no route. The response always says
which one was used — never presented as turn-by-turn directions either way.

Note: OSRM's public server is a shared free demo instance (no uptime/rate
SLA) — fine for this project's traffic, but if it ever needs to be
rock-solid, self-hosting OSRM or a paid provider would be the upgrade path.
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from services.chatbot_context import get_lgu_directory, get_spot_directory
from services.ttl_cache import TTLCache

AVG_SPEED_KMH = 35.0
ROAD_DISTANCE_FACTOR = 1.3  # straight-line -> rough road-distance approximation
_OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_LIVE_TIMEOUT_SECONDS = 6

# Coordinates don't change, so cache geocoding hits for a long time — also
# keeps us well within Nominatim's public-server usage policy (max ~1
# request/second) since a repeated place name never re-hits the network.
_geocode_cache = TTLCache(max_size=500, ttl_seconds=86400)

# Rough, deterministic one-way cost estimates — not scraped/searched, just
# published-fare-style math, same "computed and clearly labeled approximate"
# approach as the distance/ETA estimate above. Real fares/fuel prices vary
# by operator and change over time; these are for rough trip budgeting only.
FUEL_COST_PER_KM_PHP = 7.0  # ~10 km/L small car at ~PHP 70/L
BUS_BASE_FARE_PHP = 15.0  # LTFRB-style aircon bus/van minimum fare
BUS_BASE_KM = 5.0
BUS_PER_KM_PHP = 2.20


def estimate_travel_cost_php(distance_km: float) -> dict[str, int]:
    fuel_cost = round(distance_km * FUEL_COST_PER_KM_PHP)
    if distance_km <= BUS_BASE_KM:
        fare = BUS_BASE_FARE_PHP
    else:
        fare = BUS_BASE_FARE_PHP + (distance_km - BUS_BASE_KM) * BUS_PER_KM_PHP
    return {
        "fuel_cost_php": max(0, fuel_cost),
        "public_fare_php": max(0, round(fare)),
    }

# Fixed, code-level fallback origins for travelers coming from outside
# Laguna (not DB rows — we don't want to maintain a database of external
# cities, just a small set of representative points for the common nearby
# regions people actually travel from). "Quezon" and "Quezon City" can both
# be listed since _find_best_match prefers the longest matching name, so
# "I'm from Quezon City" still resolves the city specifically rather than
# the province.
_EXTERNAL_ORIGINS = [
    {"id": "_external_manila", "name": "Manila", "latitude": 14.5995, "longitude": 120.9842},
    {"id": "_external_qc", "name": "Quezon City", "latitude": 14.6760, "longitude": 121.0437},
    {"id": "_external_cavite", "name": "Cavite", "latitude": 14.4791, "longitude": 120.8970},
    {"id": "_external_batangas", "name": "Batangas", "latitude": 13.7565, "longitude": 121.0583},
    {"id": "_external_quezon", "name": "Quezon", "latitude": 13.9313, "longitude": 121.6172},
    {"id": "_external_rizal", "name": "Rizal", "latitude": 14.6042, "longitude": 121.3084},
    {"id": "_external_bulacan", "name": "Bulacan", "latitude": 14.7943, "longitude": 120.8794},
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _has_coords(row: dict[str, Any]) -> bool:
    return row.get("latitude") is not None and row.get("longitude") is not None


def _live_route_km_minutes(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> tuple[float, int] | None:
    """Real road distance/duration from OSRM (free, no key). Returns None on
    any failure (network error, no route found, server unavailable) so the
    caller falls back to the haversine estimate — this must never raise or
    block a chat reply."""
    # OSRM takes lon,lat order (not lat,lon).
    coords = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    url = f"{_OSRM_URL}/{coords}?overview=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LTCATO-LARA/1.0"})
        with urllib.request.urlopen(req, timeout=_LIVE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    if data.get("code") != "Ok":
        return None
    routes = data.get("routes") or []
    if not routes:
        return None

    distance_m = routes[0].get("distance")
    duration_s = routes[0].get("duration")
    if distance_m is None or duration_s is None:
        return None
    return round(distance_m / 1000, 1), max(1, round(duration_s / 60))


def _geocode_ph_place(name: str) -> tuple[float, float] | None:
    """Free, keyless fallback geocoder (OpenStreetMap Nominatim) for an
    origin place name that isn't a known Laguna LGU or one of the fixed
    _EXTERNAL_ORIGINS — e.g. 'Lucena' or 'Tagaytay'. Restricted to the
    Philippines to avoid wildly wrong matches. Returns None on any failure
    (never raises, never blocks a chat reply) so the caller falls back to
    asking the user for a recognized origin."""
    name = (name or "").strip()
    if not name:
        return None

    cached = _geocode_cache.get(name.lower())
    if cached is not None:
        return cached if cached != () else None

    params = urllib.parse.urlencode(
        {"q": name, "format": "json", "countrycodes": "ph", "limit": 1}
    )
    url = f"{_NOMINATIM_URL}?{params}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                # Nominatim's usage policy requires an identifying User-Agent.
                "User-Agent": "LTCATO-LARA-Chatbot/1.0 (Laguna tourism assistant)"
            },
        )
        with urllib.request.urlopen(req, timeout=_LIVE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    if not data:
        _geocode_cache.set(name.lower(), ())  # negative-cache: don't retry a bad name every message
        return None

    try:
        result = (float(data[0]["lat"]), float(data[0]["lon"]))
    except (KeyError, ValueError, TypeError, IndexError):
        return None

    _geocode_cache.set(name.lower(), result)
    return result


def _normalize_place_text(text: str) -> str:
    """Expand common Philippine place-name abbreviations so 'Santa Rosa'
    matches a DB record stored as 'Sta. Rosa', etc. Handled as two passes
    (with-period, then bare word) since a trailing '.' isn't a word-boundary
    character and would otherwise block \\b right after it."""
    text = re.sub(r"\bsta\.", "santa", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsta\b", "santa", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsto\.", "santo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsto\b", "santo", text, flags=re.IGNORECASE)
    return text


_FROM_PATTERN = re.compile(r"\bfrom\s+(.+?)(?:\s+(?:to|papunta|going to)\b|[,.!?]|$)")


def _extract_origin_phrase(blob: str) -> str | None:
    """Pull out the span after 'from' so 'how far is Cavinti from Calamba
    City' resolves Calamba (not Cavinti) as the origin — without this, two
    LGU names in one message are ambiguous and get picked by name length."""
    m = _FROM_PATTERN.search(blob)
    return m.group(1) if m else None


def _find_best_match(text_lower: str, candidates: list[dict[str, Any]], exclude_id: Any = None) -> dict[str, Any] | None:
    """Matches on the longest prefix of each candidate's name found in the
    text (down to a 2-word minimum), not just the full name — so "Siway
    River" still resolves "Siway River Bio Park" without the exact full
    listing name (same approach as chatbot_context._find_named_spot_id).
    Across candidates, the longest matched prefix wins."""
    text_lower = _normalize_place_text(text_lower)
    best: dict[str, Any] | None = None
    best_len = 0
    for c in candidates:
        name = c.get("name")
        if not name or c.get("id") == exclude_id:
            continue
        words = _normalize_place_text(name.lower()).split()
        if not words:
            continue
        min_words = min(2, len(words))
        for n in range(len(words), min_words - 1, -1):
            prefix = " ".join(words[:n])
            if re.search(r"\b" + re.escape(prefix) + r"\b", text_lower):
                if len(prefix) > best_len:
                    best = c
                    best_len = len(prefix)
                break
    return best


def resolve_route(message: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """
    Try to resolve a "distance/ETA to <spot>" question into a computed route.
    Looks at the current message plus the last few turns of history, so a
    follow-up like "I'm from Calamba" after LARA asked "where are you
    coming from?" can still resolve the spot named earlier.
    Returns None if a destination spot and an origin LGU can't both be
    confidently identified.
    """
    texts = [message] + [h.get("content") or "" for h in (history or [])[-6:]]
    blob = "\n".join(t for t in texts if t).lower()

    spots = [s for s in get_spot_directory() if _has_coords(s)]
    lgus = [l for l in get_lgu_directory() if _has_coords(l)]
    origins = lgus + _EXTERNAL_ORIGINS

    # Prefer an explicit "from <place>" phrase for the origin — without this,
    # a message naming two LGUs ("Cavinti" as destination, "Calamba City" as
    # origin) is ambiguous and _find_best_match would just pick whichever
    # name is longer, regardless of which one the user meant as origin.
    origin_phrase = _extract_origin_phrase(blob)
    origin = _find_best_match(origin_phrase, origins) if origin_phrase else None

    # A named place not in our known LGU/external lists (e.g. "Lucena",
    # "Tagaytay") — geocode it directly instead of only recognizing a fixed
    # hardcoded set of nearby regions.
    if not origin and origin_phrase:
        geocoded = _geocode_ph_place(origin_phrase)
        if geocoded:
            lat, lon = geocoded
            origin = {
                "id": f"_geocoded:{origin_phrase.strip().lower()}",
                "name": origin_phrase.strip().title(),
                "latitude": lat,
                "longitude": lon,
            }

    # Destination can be a specific attraction ("Hulugan Falls") or, if no
    # spot name matches, a whole municipality ("Cavinti") — either way we
    # already have real coordinates for it.
    destination = _find_best_match(blob, spots)
    destination_is_spot = destination is not None
    if not destination:
        exclude_id = origin.get("id") if origin else None
        destination = _find_best_match(blob, lgus, exclude_id=exclude_id)
    if not destination:
        return None

    if not origin:
        exclude_id = destination.get("lgu_id") if destination_is_spot else destination.get("id")
        origin = _find_best_match(blob, origins, exclude_id=exclude_id)
    if not origin or origin.get("id") == destination.get("id"):
        return None

    live = _live_route_km_minutes(
        origin["latitude"], origin["longitude"],
        destination["latitude"], destination["longitude"],
    )
    if live:
        road_km, eta_minutes = live
        approximate = False
    else:
        straight_km = haversine_km(
            origin["latitude"], origin["longitude"],
            destination["latitude"], destination["longitude"],
        )
        road_km = round(straight_km * ROAD_DISTANCE_FACTOR, 1)
        eta_minutes = max(5, round(road_km / AVG_SPEED_KMH * 60))
        approximate = True

    cost = estimate_travel_cost_php(road_km)

    return {
        "origin_name": origin["name"],
        "destination_name": destination["name"],
        "destination_municipality": destination.get("municipality") if destination_is_spot else None,
        "distance_km": road_km,
        "eta_minutes": eta_minutes,
        "approximate": approximate,
        "fuel_cost_php": cost["fuel_cost_php"],
        "public_fare_php": cost["public_fare_php"],
    }
