"""
Deterministic intent classification for LARA chat messages.

Keyword/regex matching only — no LLM call. This keeps retrieval scoping
free, instant, and predictable: the model never decides what data gets
fetched, it only explains data that was already fetched based on these
rules.
"""

from __future__ import annotations

import re

INTENT_SPOTS = "spots"
INTENT_EVENTS = "events"
INTENT_LGUS = "lgus"
INTENT_FAQ = "faq"
INTENT_ARRIVAL_ANALYTICS = "arrival_analytics"
INTENT_DECISION_SUPPORT = "decision_support"
INTENT_ROUTE = "route"
INTENT_GENERAL = "general"

ALL_INTENTS = (
    INTENT_SPOTS,
    INTENT_EVENTS,
    INTENT_LGUS,
    INTENT_FAQ,
    INTENT_ARRIVAL_ANALYTICS,
    INTENT_DECISION_SUPPORT,
    INTENT_ROUTE,
    INTENT_GENERAL,
)

_KEYWORDS: dict[str, tuple[str, ...]] = {
    INTENT_SPOTS: (
        "spot", "spots", "destination", "destinations", "attraction",
        "attractions", "place", "places", "waterfall", "waterfalls",
        "falls", "resort", "resorts", "beach", "beaches", "mountain",
        "mountains", "hiking", "nature", "heritage", "church", "churches",
        "shrine", "shrines", "pilgrimage", "hidden",
        "visit", "see", "recommend", "itinerary", "one day", "nearby",
        "near",
    ),
    INTENT_EVENTS: (
        "event", "events", "festival", "festivals", "fiesta", "fiestas",
        "happening", "schedule", "upcoming", "calendar",
    ),
    INTENT_LGUS: (
        "municipality", "municipalities", "city", "town", "lgu",
        "province", "laguna",
    ),
    INTENT_FAQ: (
        "faq", "how do i", "how to", "what is ltcato", "who made you",
        "who created you", "policy", "requirement", "requirements",
    ),
    INTENT_ARRIVAL_ANALYTICS: (
        "arrival", "arrivals", "tourist count", "visitor count", "visitors",
        "how many tourists", "how many visitors", "monthly total",
        "yearly total", "growth", "increase", "decrease", "compare",
        "comparison", "this month", "last month", "this year", "last year",
        "period", "report", "reports", "submission", "submissions",
        "pending report",
    ),
    INTENT_DECISION_SUPPORT: (
        "review", "reviews", "rating", "ratings", "feedback", "complaint",
        "complaints", "sentiment", "what are tourists saying",
        "what do customers", "declining", "trend", "trends", "performing",
        "performance", "insight", "insights", "recommendation for",
        "recommendations",
    ),
    INTENT_ROUTE: (
        "distance", "how far", "travel time", "eta",
        "estimated time of arrival", "how long", "directions to",
        "route to", "papaano pumunta", "malayo ba",
    ),
}


def classify_intent(message: str) -> list[str]:
    text = (message or "").lower()
    matched: list[str] = []
    for intent in (
        INTENT_SPOTS,
        INTENT_EVENTS,
        INTENT_LGUS,
        INTENT_FAQ,
        INTENT_ARRIVAL_ANALYTICS,
        INTENT_DECISION_SUPPORT,
        INTENT_ROUTE,
    ):
        for kw in _KEYWORDS[intent]:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                matched.append(intent)
                break
    if not matched:
        return [INTENT_GENERAL]
    return matched
