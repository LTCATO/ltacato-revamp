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
import urllib.request
from typing import Any

from services.chatbot_context import get_lgu_directory, get_spot_directory

AVG_SPEED_KMH = 35.0
ROAD_DISTANCE_FACTOR = 1.3  # straight-line -> rough road-distance approximation
_OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
_LIVE_TIMEOUT_SECONDS = 6

# Fixed, code-level fallback origin for travelers coming from outside Laguna
# (not a DB row — we don't want to maintain a database of external cities,
# just a single default base point when the user says they're from Manila).
_EXTERNAL_ORIGINS = [
    {"id": "_external_manila", "name": "Manila", "latitude": 14.5995, "longitude": 120.9842},
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
    text_lower = _normalize_place_text(text_lower)
    matches = [
        c
        for c in candidates
        if c.get("name") and c.get("id") != exclude_id and re.search(
            r"\b" + re.escape(_normalize_place_text(c["name"].lower())) + r"\b", text_lower
        )
    ]
    if not matches:
        return None
    # Prefer the longest/most specific name match (avoids a short LGU name
    # accidentally matching inside a longer spot name, etc.)
    matches.sort(key=lambda c: -len(c["name"]))
    return matches[0]


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

    return {
        "origin_name": origin["name"],
        "destination_name": destination["name"],
        "destination_municipality": destination.get("municipality") if destination_is_spot else None,
        "distance_km": road_km,
        "eta_minutes": eta_minutes,
        "approximate": approximate,
    }
