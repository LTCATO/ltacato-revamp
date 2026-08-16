"""
Spot & Event Insights Generator
Combines internal feedback + online reviews per spot/event.
AI (Gemini) runs only when generating missing cache rows — page load reads DB only.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from services.scrapers.sentiment_analyzer import _translate_to_english
from services.supabase_client import get_supabase

_ICON_BY_COLOR = {
    "danger": "bx-error-circle",
    "warning": "bx-info-circle",
    "info": "bx-bulb",
}

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


# ── Cached insights (Supabase generated_insights table) ─────────────────────


def _cached_entity_ids(entity_type: str) -> set[Any]:
    try:
        rows = (
            get_supabase()
            .table("generated_insights")
            .select("entity_id")
            .eq("entity_type", entity_type)
            .execute()
            .data
            or []
        )
        return {r["entity_id"] for r in rows}
    except Exception:
        return set()


def _load_cached_insights(entity_type: str) -> list[dict[str, Any]]:
    try:
        rows = (
            get_supabase()
            .table("generated_insights")
            .select("payload")
            .eq("entity_type", entity_type)
            .execute()
            .data
            or []
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            payload = row.get("payload")
            if isinstance(payload, dict) and payload:
                out.append(payload)
        out.sort(key=lambda x: (-len(x.get("issues") or []), -x.get("negative_pct", 0)))
        return out
    except Exception:
        return []


def _save_cached_insight(entity_type: str, entity_id: Any, payload: dict[str, Any]) -> bool:
    try:
        eid = int(entity_id) if str(entity_id).isdigit() else entity_id
        sb = get_supabase()
        existing = (
            sb.table("generated_insights")
            .select("id")
            .eq("entity_type", entity_type)
            .eq("entity_id", eid)
            .limit(1)
            .execute()
            .data
            or []
        )
        row = {"entity_type": entity_type, "entity_id": eid, "payload": payload}
        if existing:
            sb.table("generated_insights").update({"payload": payload}).eq(
                "id", existing[0]["id"]
            ).execute()
        else:
            sb.table("generated_insights").insert(row).execute()
        return True
    except Exception:
        return False


def _parse_ai_issues(raw: str) -> list[dict[str, Any]] | None:
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, list):
        return None
    issues: list[dict[str, Any]] = []
    for item in data[:6]:
        if not isinstance(item, dict):
            continue
        label = (item.get("label") or "").strip()
        suggestion = (item.get("suggestion") or "").strip()
        if not label or not suggestion:
            continue
        priority = (item.get("priority") or "normal").lower()
        if priority not in ("high", "normal", "low"):
            priority = "normal"
        color = (item.get("color") or "warning").lower()
        if color not in ("danger", "warning", "info"):
            color = "warning"
        icon = (item.get("icon") or _ICON_BY_COLOR.get(color, "bx-bulb")).strip()
        issues.append(
            {
                "label": label,
                "suggestion": suggestion,
                "priority": priority,
                "color": color,
                "icon": icon,
            }
        )
    return issues or None


def _ai_generate_issues(
    entity_name: str,
    entity_kind: str,
    internal_texts: list[str],
    online_texts: list[str],
) -> list[dict[str, Any]] | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    samples: list[str] = []
    for t in (internal_texts + online_texts)[:12]:
        t = (t or "").strip()
        if t and t not in samples:
            samples.append(t[:400])
    if not samples:
        return None
    internal_block = "\n".join(f"- {t}" for t in internal_texts[:8]) or "(none)"
    online_block = "\n".join(f"- {t}" for t in online_texts[:8]) or "(none)"
    prompt = f"""You are a tourism operations analyst for Laguna Province, Philippines.
Analyze negative visitor feedback for this {entity_kind}: "{entity_name}".

INTERNAL FEEDBACK (submitted on LTCATO spot/event pages):
{internal_block}

ONLINE REVIEWS (scraped from web/social):
{online_block}

Return ONLY a JSON array (no markdown prose) of 1–4 distinct issues. Each object:
{{"label": "short issue title", "suggestion": "specific actionable fix for LGU staff", "priority": "high|normal|low", "color": "danger|warning|info"}}

Base issues only on the feedback above. Be concrete and practical."""

    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1024,
                temperature=0.4,
            ),
        )
        raw = (response.text or "").strip()
        return _parse_ai_issues(raw)
    except Exception:
        return None


def get_spot_insights() -> list[dict[str, Any]]:
    """Fast page load: read cached AI insights from database only."""
    return _load_cached_insights("spot")


def get_event_insights() -> list[dict[str, Any]]:
    """Fast page load: read cached AI insights from database only."""
    return _load_cached_insights("event")


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


# ── Spot insights generation (AI + cache) ─────────────────────────────────


def _collect_spot_data() -> dict[Any, dict]:
    """Aggregate internal + online feedback per tourist spot."""
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
                    "internal_neg": [],
                    "online_neg": [],
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
                spot_data[sid]["internal_neg"].append(text)
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
            sid = row.get("tourist_spot_id")
            # Skip reviews not linked to a specific spot — they can't be saved
            if not sid:
                continue
            if sid not in spot_data:
                spot_data[sid] = {
                    "name": spot_info.get("name") or "General Review",
                    "lgu": (spot_info.get("lgus") or {}).get("name", "—"),
                    "internal_neg": [],
                    "online_neg": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            spot_data[sid]["all"] += 1
            text = (row.get("review_text") or "").strip()
            if text and row.get("sentiment") == "negative":
                spot_data[sid]["online_neg"].append(text)
                spot_data[sid]["neg"] += 1
    except Exception:
        pass
    return spot_data


def run_spot_insights_generation(force: bool = False) -> dict[str, Any]:
    """
    AI-generate spot insights from internal + online feedback.
    Skips spots already stored in generated_insights unless force=True.
    """
    cached_ids = set() if force else _cached_entity_ids("spot")
    spot_data = _collect_spot_data()
    generated = 0
    skipped = 0
    errors: list[str] = []

    for sid, data in spot_data.items():
        if sid in cached_ids:
            skipped += 1
            continue
        internal_neg = data.get("internal_neg") or []
        online_neg = data.get("online_neg") or []
        if not internal_neg and not online_neg:
            continue

        issues = _ai_generate_issues(
            data["name"], "tourist spot", internal_neg, online_neg
        )
        if not issues:
            combined = internal_neg + online_neg
            detected_keys = _detect_issues(combined, ISSUE_MAP)
            if not detected_keys:
                continue
            detected_keys.sort(
                key=lambda k: _PRIORITY_ORDER.get(ISSUE_MAP[k]["priority"], 99)
            )
            issues = [_build_issue_card(k, ISSUE_MAP) for k in detected_keys]

        ratings = data["ratings"]
        payload = {
            "spot_id": sid,
            "spot_name": data["name"],
            "lgu_name": data["lgu"],
            "total_feedback": data["all"],
            "negative_count": data["neg"],
            "negative_pct": round(data["neg"] / data["all"] * 100, 1)
            if data["all"]
            else 0,
            "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "issues": issues,
        }
        if _save_cached_insight("spot", sid, payload):
            generated += 1
        else:
            errors.append(f"Could not save insight for spot {data['name']}")

    return {"ok": True, "generated": generated, "skipped": skipped, "errors": errors}


# ── Event insights generation (AI + cache) ────────────────────────────────


def _collect_event_data() -> dict[Any, dict]:
    """Aggregate internal event feedback + online reviews per event."""
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
                    "internal_neg": [],
                    "online_neg": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            event_data[eid]["all"] += 1
            r = row.get("rating") or 0
            if r:
                event_data[eid]["ratings"].append(r)
            text = (row.get("comment") or "").strip()
            if text and r <= 3:
                event_data[eid]["internal_neg"].append(text)
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
                    "internal_neg": [],
                    "online_neg": [],
                    "all": 0,
                    "neg": 0,
                    "ratings": [],
                }
            event_data[eid]["all"] += 1
            text = (row.get("review_text") or "").strip()
            if text and row.get("sentiment") == "negative":
                event_data[eid]["online_neg"].append(text)
                event_data[eid]["neg"] += 1
    except Exception:
        pass
    return event_data


def run_event_insights_generation(force: bool = False) -> dict[str, Any]:
    """
    AI-generate event insights from internal feedback + online coverage.
    Skips events already in generated_insights unless force=True.
    """
    cached_ids = set() if force else _cached_entity_ids("event")
    event_data = _collect_event_data()
    generated = 0
    skipped = 0
    errors: list[str] = []

    for eid, data in event_data.items():
        if eid in cached_ids:
            skipped += 1
            continue
        internal_neg = data.get("internal_neg") or []
        online_neg = data.get("online_neg") or []
        if not internal_neg and not online_neg:
            continue

        issues = _ai_generate_issues(
            data["title"], "tourism event", internal_neg, online_neg
        )
        if not issues:
            combined = internal_neg + online_neg
            detected_keys = _detect_issues(combined, EVENT_ISSUE_MAP)
            if not detected_keys:
                continue
            detected_keys.sort(
                key=lambda k: _PRIORITY_ORDER.get(EVENT_ISSUE_MAP[k]["priority"], 99)
            )
            issues = [_build_issue_card(k, EVENT_ISSUE_MAP) for k in detected_keys]

        ratings = data["ratings"]
        payload = {
            "event_id": eid,
            "event_title": data["title"],
            "lgu_name": data["lgu"],
            "event_status": data["status"],
            "total_feedback": data["all"],
            "negative_count": data["neg"],
            "negative_pct": round(data["neg"] / data["all"] * 100, 1)
            if data["all"]
            else 0,
            "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "issues": issues,
        }
        if _save_cached_insight("event", eid, payload):
            generated += 1
        else:
            errors.append(f"Could not save insight for event {data['title']}")

    return {"ok": True, "generated": generated, "skipped": skipped, "errors": errors}


def run_insights_generation(force: bool = False) -> dict[str, Any]:
    """Generate missing spot + event insights (AI with template fallback)."""
    spot = run_spot_insights_generation(force=force)
    event = run_event_insights_generation(force=force)
    return {
        "ok": True,
        "generated": spot.get("generated", 0) + event.get("generated", 0),
        "skipped": spot.get("skipped", 0) + event.get("skipped", 0),
        "spot": spot,
        "event": event,
        "errors": (spot.get("errors") or []) + (event.get("errors") or []),
    }
