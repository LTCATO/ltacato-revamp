"""
Spot & Event Insights Generator
Analyzes combined internal + online feedback per tourist spot and event,
detects recurring issue themes, and generates specific actionable suggestions.

AI (Gemini) is NOT called during page load — only template suggestions are used.
This keeps the page fast (~2s load). AI integration can be added as a background job.
"""

from __future__ import annotations

from typing import Any

from services.scrapers.sentiment_analyzer import _translate_to_english
from services.supabase_client import get_supabase

# ── Spot issue detection map ──────────────────────────────────────────────
ISSUE_MAP: dict[str, dict] = {
    "cleanliness": {
        "keywords": [
            "dirty",
            "smelly",
            "smell bad",
            "stinks",
            "stink",
            "filthy",
            "trash",
            "garbage",
            "litter",
            "littered",
            "rubbish",
            "waste",
            "unhygienic",
            "disgusting",
            "unsanitary",
            "mud",
            "muddy",
            "messy",
            "smell",
            "odor",
            "stinky",
            "foul",
            "polluted",
        ],
        "label": "Cleanliness & Hygiene",
        "suggestion": (
            "Implement a strict daily cleaning schedule (morning and afternoon). "
            "Add more trash bins at entry points and high-traffic areas. "
            "Assign dedicated sanitation staff and post clear 'No Littering' notices."
        ),
        "icon": "bx-trash",
        "priority": "high",
        "color": "danger",
    },
    "facility": {
        "keywords": [
            "broken",
            "damaged",
            "old",
            "run-down",
            "dilapidated",
            "needs repair",
            "deteriorating",
            "falling apart",
            "poor condition",
            "crumbling",
            "neglected",
            "worn out",
            "rusty",
            "not working",
            "maintenance",
            "repair",
            "old",
            "worn",
            "deteriorated",
        ],
        "label": "Facility Condition",
        "suggestion": (
            "Conduct a full facility audit this quarter. "
            "Create a maintenance priority list and allocate budget for urgent repairs. "
            "Establish a monthly inspection routine logged in an official maintenance record."
        ),
        "icon": "bx-wrench",
        "priority": "normal",
        "color": "warning",
    },
    "crowding": {
        "keywords": [
            "crowded",
            "overcrowded",
            "too many people",
            "packed",
            "long queue",
            "long line",
            "waiting time",
            "noisy",
            "chaotic",
            "lot of people",
            "lots of people",
            "so many people",
            "many people",
            "full",
            "overflowing",
            "congested",
            "busy",
            "rush",
        ],
        "label": "Overcrowding",
        "suggestion": (
            "Introduce timed entry slots via online reservation. "
            "Set a daily visitor capacity limit. "
            "Deploy crowd management staff at peak hours (weekends and holidays)."
        ),
        "icon": "bx-group",
        "priority": "normal",
        "color": "warning",
    },
    "pricing": {
        "keywords": [
            "expensive",
            "overpriced",
            "costly",
            "pricey",
            "too expensive",
            "not worth",
            "ripoff",
            "rip off",
            "unreasonable price",
            "too much",
            "price",
            "fee",
            "charge",
            "cost",
        ],
        "label": "Pricing Concerns",
        "suggestion": (
            "Review and compare entrance fee structures with similar destinations. "
            "Introduce tiered pricing for locals, students, and senior citizens. "
            "Bundle amenities (parking, restroom, guide) to increase perceived value."
        ),
        "icon": "bx-money",
        "priority": "low",
        "color": "info",
    },
    "safety": {
        "keywords": [
            "unsafe",
            "dangerous",
            "hazardous",
            "no safety",
            "accident",
            "slippery",
            "no guard",
            "no lifeguard",
            "no security",
            "risky",
            "perilous",
            "unguarded",
            "dark",
            "no lighting",
        ],
        "label": "Safety & Security",
        "suggestion": (
            "Deploy trained safety officers during all operating hours. "
            "Install visible warning signs, barriers, and emergency contact numbers. "
            "Conduct monthly safety drills and visitor safety briefings at entry."
        ),
        "icon": "bx-shield-x",
        "priority": "high",
        "color": "danger",
    },
    "staff": {
        "keywords": [
            "rude",
            "unprofessional",
            "unfriendly",
            "unhelpful",
            "staff",
            "bad service",
            "poor service",
            "no assistance",
            "arrogant",
            "impolite",
            "disrespectful",
            "not helpful",
            "no help",
        ],
        "label": "Staff Conduct",
        "suggestion": (
            "Conduct mandatory customer service and hospitality training. "
            "Establish a written code of conduct for all staff. "
            "Install a visitor feedback kiosk so tourists can rate staff interactions."
        ),
        "icon": "bx-user-x",
        "priority": "high",
        "color": "danger",
    },
    "access": {
        "keywords": [
            "hard to reach",
            "no parking",
            "no transportation",
            "poor signage",
            "no signs",
            "confusing",
            "lost",
            "no directions",
            "inaccessible",
            "far",
            "hard to find",
            "difficult",
            "no access",
        ],
        "label": "Accessibility",
        "suggestion": (
            "Install clear directional signage from major roads. "
            "Coordinate with local transport cooperatives for shuttle services. "
            "Add detailed travel guide and maps to the official tourism page."
        ),
        "icon": "bx-car",
        "priority": "normal",
        "color": "warning",
    },
    "amenities": {
        "keywords": [
            "no toilet",
            "no restroom",
            "no comfort room",
            "no bathroom",
            "no water",
            "no drinking water",
            "no shade",
            "no seats",
            "no benches",
            "no facilities",
            "lack of amenities",
            "no cr",
            "no comfort",
            "no rest area",
        ],
        "label": "Lack of Basic Amenities",
        "suggestion": (
            "Install or upgrade restroom facilities to meet minimum sanitation standards. "
            "Add drinking water stations and covered rest areas. "
            "Provide visitor information boards at the entrance."
        ),
        "icon": "bx-building",
        "priority": "high",
        "color": "danger",
    },
    "quality": {
        "keywords": [
            "disappointing",
            "not worth it",
            "boring",
            "nothing to see",
            "waste of time",
            "not impressive",
            "overrated",
            "terrible",
            "awful",
            "horrible",
            "bad experience",
            "poor",
            "ugly",
            "panget",
            "hindi maganda",
        ],
        "label": "Visitor Experience Quality",
        "suggestion": (
            "Develop engaging visitor activities and educational programs. "
            "Improve interpretive signage and guided tour options. "
            "Gather specific feedback from disappointed visitors to identify gaps."
        ),
        "icon": "bx-dislike",
        "priority": "normal",
        "color": "warning",
    },
}

# ── Event issue detection map ─────────────────────────────────────────────
EVENT_ISSUE_MAP: dict[str, dict] = {
    "organization": {
        "keywords": [
            "disorganized",
            "chaotic",
            "poor planning",
            "no coordination",
            "confusing",
            "poorly managed",
            "no system",
            "messy",
            "disorder",
            "disarray",
            "unorganized",
            "uncoordinated",
            "no order",
            "scattered",
            "no management",
            "badly managed",
        ],
        "label": "Event Organization",
        "suggestion": (
            "Create a detailed event management plan with a timeline and volunteer assignments. "
            "Conduct a pre-event dry run and briefing with all staff and volunteers."
        ),
        "icon": "bx-calendar-x",
        "priority": "high",
        "color": "danger",
    },
    "timing": {
        "keywords": [
            "late",
            "delayed",
            "started late",
            "no schedule",
            "overtime",
            "too long",
            "too short",
            "behind schedule",
            "not on time",
            "postponed",
            "rescheduled",
            "slow",
            "waited",
            "waiting",
        ],
        "label": "Schedule & Timing",
        "suggestion": (
            "Publish a strict program schedule at least 2 weeks in advance. "
            "Assign a dedicated time-keeper and communicate any delays via announcements immediately."
        ),
        "icon": "bx-time",
        "priority": "normal",
        "color": "warning",
    },
    "crowd_control": {
        "keywords": [
            "crowded",
            "overcrowded",
            "no crowd control",
            "pushing",
            "too packed",
            "stampede risk",
            "lot of people",
            "lots of people",
            "so many people",
            "many people",
            "full",
            "overflowing",
            "no space",
            "tight",
            "compressed",
            "shoulder to shoulder",
            "daming tao",
            "maraming tao",
        ],
        "label": "Crowd Management",
        "suggestion": (
            "Implement a ticket-based entry with capacity limits. "
            "Deploy trained crowd marshals and create clear entry, exit, and emergency routes."
        ),
        "icon": "bx-group",
        "priority": "high",
        "color": "danger",
    },
    "venue": {
        "keywords": [
            "wrong venue",
            "too small",
            "venue problem",
            "no seats",
            "not comfortable",
            "poor venue",
            "bad location",
            "too far",
            "venue too small",
            "not enough space",
            "uncomfortable",
        ],
        "label": "Venue Issues",
        "suggestion": (
            "Conduct an advance venue inspection and capacity assessment. "
            "Ensure adequate seating, parking, and emergency exits for the projected attendance."
        ),
        "icon": "bx-map",
        "priority": "normal",
        "color": "warning",
    },
    "content": {
        "keywords": [
            "boring",
            "poor entertainment",
            "nothing to do",
            "disappointing",
            "not engaging",
            "no activities",
            "waste of time",
            "uninteresting",
            "dull",
            "not fun",
            "no program",
            "nothing happening",
        ],
        "label": "Program Content",
        "suggestion": (
            "Survey attendees on preferred activities before the next event. "
            "Include interactive, cultural, and local-themed segments to boost engagement."
        ),
        "icon": "bx-confused",
        "priority": "normal",
        "color": "warning",
    },
    "facilities": {
        "keywords": [
            "no toilet",
            "no restroom",
            "no comfort room",
            "no food",
            "no water",
            "no parking",
            "no shade",
            "lack of amenities",
            "no cr",
            "no vendors",
            "no stalls",
            "hungry",
        ],
        "label": "Event Facilities",
        "suggestion": (
            "Arrange adequate portable restrooms, food stalls, water stations, "
            "and designated parking proportional to event-day attendance estimates."
        ),
        "icon": "bx-building",
        "priority": "high",
        "color": "danger",
    },
    "communication": {
        "keywords": [
            "no information",
            "no announcement",
            "poor communication",
            "no update",
            "no notice",
            "not informed",
            "unclear",
            "no details",
            "no notice",
            "not advertised",
            "confusing",
        ],
        "label": "Event Communication",
        "suggestion": (
            "Publish complete event details (schedule, venue, program) on all social channels "
            "at least 2 weeks before. Assign a dedicated communications officer for real-time updates."
        ),
        "icon": "bx-broadcast",
        "priority": "normal",
        "color": "warning",
    },
    "quality": {
        "keywords": [
            "disappointing",
            "not worth it",
            "boring",
            "terrible",
            "awful",
            "horrible",
            "bad",
            "poor quality",
            "not good",
            "waste of time",
            "hindi maganda",
            "pangit",
            "hindi masaya",
        ],
        "label": "Event Quality",
        "suggestion": (
            "Conduct a post-event survey to identify specific pain points. "
            "Benchmark against successful events of similar scale and improve weak areas."
        ),
        "icon": "bx-dislike",
        "priority": "normal",
        "color": "warning",
    },
}

_PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


def _detect_issues(texts: list[str], issue_map: dict) -> list[str]:
    """Detect issue categories from feedback texts (translates to English first)."""
    if not texts:
        return []
    combined = ""
    for t in texts:
        try:
            translated = _translate_to_english(t)
            combined += " " + translated.lower()
        except Exception:
            combined += " " + t.lower()
    # Also include original text for direct Tagalog keyword matching
    for t in texts:
        combined += " " + t.lower()
    return [
        k for k, v in issue_map.items() if any(kw in combined for kw in v["keywords"])
    ]


def _build_issue_card(key: str, issue_map: dict) -> dict:
    """Build an issue card using template suggestion (no AI calls for speed)."""
    data = issue_map[key]
    return {
        "key": key,
        "label": data["label"],
        "suggestion": data["suggestion"],
        "icon": data["icon"],
        "priority": data["priority"],
        "color": data["color"],
    }


# ── Spot insights ──────────────────────────────────────────────────────────


def generate_spot_insights() -> list[dict[str, Any]]:
    """
    Generate per-spot insights from internal feedbacks + external reviews.
    Fetches ALL feedbacks grouped by tourist_spot_id regardless of approval status.
    NOTE: No AI calls — uses template suggestions for speed.
    """
    spot_data: dict[Any, dict] = {}

    # Internal feedbacks
    try:
        for row in (
            get_supabase()
            .table("feedbacks")
            .select(
                "comments, suggestions, sentiment, rating, "
                "tourist_spot_id, tourist_spots(id, name, lgus(name))"
            )
            .execute()
            .data
            or []
        ):
            spot_info = row.get("tourist_spots") or {}
            sid = row.get("tourist_spot_id") or "general"
            if sid not in spot_data:
                spot_data[sid] = {
                    "name": spot_info.get("name") or "Unknown Spot",
                    "lgu": (spot_info.get("lgus") or {}).get("name", "—"),
                    "neg_texts": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            spot_data[sid]["all"] += 1
            r = row.get("rating") or 0
            if r:
                spot_data[sid]["ratings"].append(r)
            text = " ".join(
                filter(None, [row.get("comments"), row.get("suggestions")])
            ).strip()
            if text and (row.get("sentiment") == "negative" or r <= 2):
                spot_data[sid]["neg_texts"].append(text)
                spot_data[sid]["neg"] += 1
    except Exception:
        pass

    # External reviews (online + Facebook) — only spot reviews
    try:
        q = (
            get_supabase()
            .table("external_reviews")
            .select(
                "review_text, sentiment, tourist_spot_id, "
                "tourist_spots(id, name, lgus(name))"
            )
        )
        try:
            q = q.is_("event_id", "null")
        except Exception:
            pass
        for row in q.execute().data or []:
            spot_info = row.get("tourist_spots") or {}
            sid = row.get("tourist_spot_id") or "general"
            if sid not in spot_data:
                spot_data[sid] = {
                    "name": spot_info.get("name") or "General Review",
                    "lgu": (spot_info.get("lgus") or {}).get("name", "—"),
                    "neg_texts": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            spot_data[sid]["all"] += 1
            text = (row.get("review_text") or "").strip()
            if text and row.get("sentiment") == "negative":
                spot_data[sid]["neg_texts"].append(text)
                spot_data[sid]["neg"] += 1
    except Exception:
        pass

    insights: list[dict] = []
    for sid, data in spot_data.items():
        if not data["neg_texts"]:
            continue
        detected_keys = _detect_issues(data["neg_texts"], ISSUE_MAP)
        if not detected_keys:
            continue
        detected_keys.sort(
            key=lambda k: _PRIORITY_ORDER.get(ISSUE_MAP[k]["priority"], 99)
        )
        ratings = data["ratings"]
        insights.append(
            {
                "spot_id": sid,
                "spot_name": data["name"],
                "lgu_name": data["lgu"],
                "total_feedback": data["all"],
                "negative_count": data["neg"],
                "negative_pct": round(data["neg"] / data["all"] * 100, 1)
                if data["all"]
                else 0,
                "avg_rating": round(sum(ratings) / len(ratings), 1)
                if ratings
                else None,
                "issues": [_build_issue_card(k, ISSUE_MAP) for k in detected_keys],
            }
        )
    insights.sort(key=lambda x: (-len(x["issues"]), -x["negative_pct"]))
    return insights


# ── Event insights ─────────────────────────────────────────────────────────


def generate_event_insights() -> list[dict[str, Any]]:
    """
    Generate per-event insights from:
    1. Internal event_feedbacks (ALL comments with text, not just low ratings)
    2. External reviews with event_id set (Facebook + online)
    NOTE: No AI calls — uses template suggestions for speed.
    """
    event_data: dict[Any, dict] = {}

    # Internal event_feedbacks — include ALL comments that have text
    try:
        for row in (
            get_supabase()
            .table("event_feedbacks")
            .select(
                "comment, rating, event_id, events(id, title, event_status, lgus(name))"
            )
            .execute()
            .data
            or []
        ):
            ev_info = row.get("events") or {}
            eid = row.get("event_id") or ev_info.get("id")
            if not eid:
                continue
            if eid not in event_data:
                event_data[eid] = {
                    "title": ev_info.get("title") or f"Event #{eid}",
                    "lgu": (ev_info.get("lgus") or {}).get("name", "—"),
                    "status": ev_info.get("event_status") or "unknown",
                    "neg_texts": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            event_data[eid]["all"] += 1
            r = row.get("rating") or 0
            if r:
                event_data[eid]["ratings"].append(r)
            text = (row.get("comment") or "").strip()
            if text:
                # Include comment if: low rating (≤3) OR has negative sentiment words
                if r <= 3:
                    event_data[eid]["neg_texts"].append(text)
                    event_data[eid]["neg"] += 1
    except Exception:
        pass

    # External reviews with event_id (Facebook posts + online coverage)
    try:
        rows = (
            get_supabase()
            .table("external_reviews")
            .select(
                "review_text, sentiment, event_id, "
                "events(id, title, event_status, lgus(name))"
            )
            .not_.is_("event_id", "null")
            .execute()
            .data
            or []
        )
        for row in rows:
            ev_info = row.get("events") or {}
            eid = row.get("event_id")
            if not eid:
                continue
            if eid not in event_data:
                event_data[eid] = {
                    "title": ev_info.get("title") or f"Event #{eid}",
                    "lgu": (ev_info.get("lgus") or {}).get("name", "—"),
                    "status": ev_info.get("event_status") or "unknown",
                    "neg_texts": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            event_data[eid]["all"] += 1
            text = (row.get("review_text") or "").strip()
            if text and row.get("sentiment") == "negative":
                event_data[eid]["neg_texts"].append(text)
                event_data[eid]["neg"] += 1
    except Exception:
        pass

    insights: list[dict] = []
    for eid, data in event_data.items():
        if not data["neg_texts"]:
            continue
        detected_keys = _detect_issues(data["neg_texts"], EVENT_ISSUE_MAP)
        if not detected_keys:
            continue
        detected_keys.sort(
            key=lambda k: _PRIORITY_ORDER.get(EVENT_ISSUE_MAP[k]["priority"], 99)
        )
        ratings = data["ratings"]
        insights.append(
            {
                "event_id": eid,
                "event_title": data["title"],
                "lgu_name": data["lgu"],
                "event_status": data["status"],
                "total_feedback": data["all"],
                "negative_count": data["neg"],
                "negative_pct": round(data["neg"] / data["all"] * 100, 1)
                if data["all"]
                else 0,
                "avg_rating": round(sum(ratings) / len(ratings), 1)
                if ratings
                else None,
                "issues": [
                    _build_issue_card(k, EVENT_ISSUE_MAP) for k in detected_keys
                ],
            }
        )
    insights.sort(key=lambda x: (-len(x["issues"]), -x["negative_pct"]))
    return insights
