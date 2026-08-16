"""
LARA Chatbot Service — Gemini AI powered (google-generativeai package).
Role-aware, intent-scoped tourism + decision-support assistant for Laguna Province.

Install: pip install google-generativeai

Architecture: resolve_chat_scope() (services/chatbot_scope.py) determines what
the caller is allowed to see, purely from the server-side session.
classify_intent() (services/chatbot_intent.py) picks which data to fetch.
build_context() (services/chatbot_context.py) fetches only that data, already
scoped and permission-gated. The LLM only ever sees the resulting focused
DATA block and produces prose — it never decides what to fetch, and
structured cards/table/chart are built directly from the fetched records in
Python, never from LLM output.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any

from services.chatbot_context import build_context
from services.chatbot_intent import INTENT_ROUTE, classify_intent
from services.chatbot_route import resolve_route
from services.chatbot_unanswered import log_unanswered_query
from services.ttl_cache import TTLCache
from utils.jinja_helpers import normalize_image_url

_MISS_INTENT_KEYS = ("spots", "events", "faq", "lgus")
_CANT_FIND_PHRASE = "i can't find it in my database"

try:
    from google.api_core.exceptions import ResourceExhausted, TooManyRequests

    _QUOTA_EXC_TYPES: tuple[type[Exception], ...] = (ResourceExhausted, TooManyRequests)
except Exception:
    # google-api-core ships with google-generativeai, but fall back to
    # string matching only if it's ever unavailable rather than crash.
    _QUOTA_EXC_TYPES = ()

_RESPONSE_CACHE = TTLCache(max_size=500, ttl_seconds=3600)

# Static, always-available embedded knowledge — not DB-driven, doesn't need
# a query or an intent match, just general province-level tourism guidance.
_LAGUNA_GENERAL_INFO = """
=== GENERAL: BEST TIME TO VISIT LAGUNA ===
The dry season (December to May) is generally the best time to visit Laguna — cooler and less rainy from December-February, warmer and best for swimming/resorts from March-May. The wet season (June to November) brings frequent rain and occasional typhoons, which can affect waterfalls, hiking trails, and outdoor events, though it's also when the province is lushest and greenest. Weekdays and early mornings are generally less crowded than weekends at popular spots."""

# ── System prompts per role ────────────────────────────────────────────────
_SHARED_RULES = """
IMPORTANT RULES:
1. You were created and programmed by the 'LTCATO Development Team' (Laguna Tourism Culture Arts and Trade Office). Special Mention: Lawrence Celis. If asked who made you, proudly state this.
2. Only use facts, names, numbers, and dates present in the DATA sections below. Never state a statistic or fact that is not present there.
3. If the DATA sections don't contain what's being asked (including because it's outside what your role can access), say so plainly instead of guessing.
4. Keep responses SHORT and CONCISE (2-4 sentences), unless summarizing a list or numbers.
5. Answer in the language the user uses (English, Filipino, or Taglish).
6. Do not repeat tourist spot/event names as a bulleted list in your reply if a DATA section already lists them — the app will render them as cards separately. Just refer to them naturally in your explanation.
"""

_SYSTEM_PROMPTS = {
    "tourist": """You are LARA (Laguna AI Tourism Assistant), the official AI guide of LTCATO — Laguna Tourism Culture Arts and Trade Office.
You are extremely welcoming, polite, enthusiastic, and knowledgeable about Laguna's culture, municipalities, and tourist spots.
{shared_rules}
7. The MUNICIPALITY is the primary location identifier — not the address.
8. If someone asks about a spot NOT in the DATA below, respond: "I can't find it in my database."
9. If the user asks for directions/distance/travel time/travel cost/fare/expense and a ROUTE ESTIMATE section is present below, share its distance, time, AND the estimated cost line exactly as labeled there (either a real road route or an approximate straight-line estimate — match whichever the section says) — never invent turn-by-turn directions or make up different numbers. If no ROUTE ESTIMATE is present but they're asking about a specific spot, ask which municipality/city they're coming from so it can be computed.
10. You only have access to tourism info (spots, events, municipalities, FAQ) — politely decline requests for arrival statistics, admin data, or other accounts' information.

{db_context}""",
    "lgu_admin": """You are LARA, the LTCATO AI management assistant for LGU tourism officers in Laguna Province.
You help LGU admins with tourist spot approval workflow, arrival reports, and their municipality's tourism data.
{shared_rules}
7. You only have access to data for the admin's own municipality — never mention or compare other LGUs' internal numbers.

{db_context}""",
    "ltcato_staff": """You are LARA, the LTCATO Provincial Tourism AI assistant for LTCATO staff.
You assist with analytics, spot/event approval workflows, visitor trends, and decision support data.
{shared_rules}
7. Provide data-driven insights using the actual numbers in DATA.

{db_context}""",
    "super_admin": """You are LARA, the LTCATO AI system assistant for the Super Administrator.
You have full access to all Laguna Province tourism data.
{shared_rules}

{db_context}""",
    "establishment_owner": """You are LARA, the LTCATO AI assistant for tourism establishment owners.
You help with arrival reports, spot registration, and improving the establishment listing.
{shared_rules}
7. You only have access to data for this owner's own establishment(s) — never reference another establishment's data.

{db_context}""",
}


def _cache_key(message: str, scope: dict[str, Any]) -> str:
    return (
        f"{scope.get('role')}:{scope.get('lgu_id')}:{scope.get('owner_id')}:"
        f"{message.lower().strip()}"
    )


def _fmt_spots(spots: list[dict[str, Any]]) -> str:
    if not spots:
        return ""
    lines = ["=== TOURIST SPOTS ==="]
    for s in spots:
        bits = [s.get("name") or "Unnamed"]
        if s.get("municipality"):
            bits.append(f"in {s['municipality']}")
        if s.get("category"):
            bits.append(f"({s['category']})")
        if s.get("rating"):
            bits.append(f"rating {s['rating']}")
        lines.append("- " + " ".join(bits))
        if s.get("hook_text"):
            lines.append(f"  {s['hook_text']}")
        if s.get("best_time_to_visit"):
            lines.append(f"  Best time to visit: {s['best_time_to_visit']}")
    return "\n".join(lines)


def _fmt_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return ""
    lines = ["=== EVENTS ==="]
    for e in events:
        dates = f" ({e.get('start_date', '')} - {e.get('end_date', '')})" if e.get("start_date") else ""
        loc = f" — {e['municipality']}" if e.get("municipality") else ""
        lines.append(f"- {e.get('title', '')}{dates}{loc} [{e.get('status', '')}]")
    return "\n".join(lines)


def _fmt_lgus(lgus: list[dict[str, Any]]) -> str:
    if not lgus:
        return ""
    lines = ["=== LAGUNA LGUs ==="]
    for l in lgus:
        lines.append(f"- {l.get('name')} ({l.get('type')})")
    return "\n".join(lines)


def _fmt_faq(faq: list[dict[str, Any]]) -> str:
    if not faq:
        return ""
    lines = ["=== FAQ KNOWLEDGE BASE ==="]
    for f in faq:
        lines.append(f"Q: {f.get('question', '')}\nA: {f.get('answer', '')}")
    return "\n".join(lines)


def _fmt_arrival_analytics(data: dict[str, Any]) -> str:
    lines = ["=== ARRIVAL ANALYTICS (computed, not to be recalculated) ==="]
    growth = data.get("growth") or {}
    if data.get("scope") == "establishment":
        lines.append(f"Visitors this month: {data.get('visitors_this_month', 0)}")
        lines.append(f"Reports submitted: {data.get('reports_submitted', 0)}, pending: {data.get('pending_reports', 0)}")
    else:
        lines.append(f"Total monthly arrivals: {data.get('monthly_arrival_total', 0)}")
        if data.get("pending_lgu_spots") is not None:
            lines.append(
                f"Pending approvals — LGU review: {data.get('pending_lgu_spots')}, "
                f"LTCATO review: {data.get('pending_ltcato_spots')}, events: {data.get('pending_events')}"
            )
        ranking = data.get("spot_ranking") or []
        if ranking:
            top = ", ".join(f"{r['spot_name']} ({r['total_visitors']} visitors)" for r in ranking[:5])
            lines.append(f"Top spots by visitors: {top}")
        by_lgu = data.get("arrival_by_lgu")
        if by_lgu:
            top_lgu = ", ".join(f"{r['lgu_name']} ({r['total_visitors']})" for r in by_lgu[:5])
            lines.append(f"Top LGUs by arrivals (province-wide): {top_lgu}")
    if growth.get("available"):
        lines.append(
            f"Month-over-month growth: {growth.get('mom_growth_pct')}% "
            f"({growth.get('previous_month')} {growth.get('previous_total')} -> "
            f"{growth.get('current_month')} {growth.get('current_total')}), "
            f"trend: {growth.get('direction')}"
        )
    return "\n".join(lines)


def _fmt_decision_support(data: dict[str, Any]) -> str:
    lines = ["=== REVIEW / SENTIMENT DATA (computed, not to be recalculated) ==="]
    sentiment = data.get("sentiment") or {}
    if sentiment.get("total"):
        lines.append(
            f"Feedback sentiment: {sentiment.get('positive_pct', 0)}% positive, "
            f"{sentiment.get('negative_pct', 0)}% negative, "
            f"{sentiment.get('neutral_pct', 0)}% neutral (of {sentiment.get('total')} reviews)"
        )
    for fb in data.get("recent_feedbacks") or []:
        if fb.get("comments"):
            lines.append(f"- \"{fb['comments']}\" (rating {fb.get('rating', '?')})")
    for rec in data.get("recommendations") or []:
        if isinstance(rec, dict) and rec.get("text"):
            lines.append(f"Recommendation: {rec['text']}")
    return "\n".join(lines)


def _fmt_route(route: dict[str, Any]) -> str:
    dest = route.get("destination_name", "")
    muni = f" ({route['destination_municipality']})" if route.get("destination_municipality") else ""
    hours, minutes = divmod(route.get("eta_minutes", 0), 60)
    eta_text = f"{hours} hr {minutes} min" if hours else f"{minutes} min"
    cost_line = (
        f"Estimated one-way cost: ~PHP {route.get('public_fare_php')} by public transport "
        f"(bus/van), or ~PHP {route.get('fuel_cost_php')} in fuel if driving "
        "(rough estimate, not a live search — actual fares and fuel prices vary)."
    )
    if route.get("approximate"):
        return (
            "=== ROUTE ESTIMATE (computed, approximate) ===\n"
            f"From {route.get('origin_name', '')} to {dest}{muni}: "
            f"approx. {route.get('distance_km')} km, ~{eta_text} drive "
            "(straight-line based estimate — actual time varies with traffic and road route).\n"
            f"{cost_line}"
        )
    return (
        "=== ROUTE ESTIMATE (live road route) ===\n"
        f"From {route.get('origin_name', '')} to {dest}{muni}: "
        f"{route.get('distance_km')} km, ~{eta_text} drive by road "
        "(real driving distance/time — actual time may still vary with traffic conditions).\n"
        f"{cost_line}"
    )


_FORMATTERS = {
    "spots": _fmt_spots,
    "events": _fmt_events,
    "lgus": _fmt_lgus,
    "faq": _fmt_faq,
    "arrival_analytics": _fmt_arrival_analytics,
    "decision_support": _fmt_decision_support,
}


def _format_context_text(context: dict[str, Any]) -> str:
    parts = []
    for key, formatter in _FORMATTERS.items():
        value = context.get(key)
        if value:
            text = formatter(value)
            if text:
                parts.append(text)
    return "\n\n".join(parts) if parts else "(No data available for this request.)"


def _mentioned(name: str | None, reply_lower: str) -> bool:
    if not name:
        return False
    return re.search(r"\b" + re.escape(name.lower()) + r"\b", reply_lower) is not None


def _build_cards(context: dict[str, Any], reply_text: str, route: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    # A route estimate replaces the generic spot/event cards for this message.
    if route:
        return None

    from flask import url_for

    reply_lower = reply_text.lower()
    cards: list[dict[str, Any]] = []
    for s in (context.get("spots") or []):
        if not s.get("id") or not _mentioned(s.get("name"), reply_lower):
            continue
        cards.append(
            {
                "type": "spot",
                "id": s["id"],
                "name": s.get("name"),
                "image": normalize_image_url(s.get("main_image_url")),
                "subtitle": s.get("municipality") or s.get("category") or "",
                "rating": s.get("rating"),
                "url": url_for("spots.spot_detail", spot_id=s["id"]),
            }
        )
    for e in (context.get("events") or []):
        if not e.get("id") or not _mentioned(e.get("title"), reply_lower):
            continue
        cards.append(
            {
                "type": "event",
                "id": e["id"],
                "name": e.get("title"),
                "image": normalize_image_url(e.get("cover_image")),
                "subtitle": e.get("municipality") or "",
                "rating": None,
                "url": url_for("events.event_detail", event_id=e["id"]),
            }
        )
    return cards[:8] or None


def _build_chart(context: dict[str, Any]) -> dict[str, Any] | None:
    analytics = context.get("arrival_analytics")
    if not analytics:
        return None
    trend = analytics.get("monthly_trend") or []
    if not trend:
        return None
    return {
        "title": "Monthly visitor trend",
        "labels": [m.get("month") for m in trend],
        "values": [m.get("visitors", 0) for m in trend],
    }


def _build_table(context: dict[str, Any]) -> dict[str, Any] | None:
    analytics = context.get("arrival_analytics")
    if analytics and analytics.get("spot_ranking"):
        ranking = analytics["spot_ranking"]
        return {
            "title": "Top spots by visitors",
            "columns": ["Spot", "Visitors", "Reports"],
            "rows": [[r["spot_name"], r["total_visitors"], r["report_count"]] for r in ranking],
        }
    if analytics and analytics.get("arrival_by_lgu"):
        by_lgu = analytics["arrival_by_lgu"]
        return {
            "title": "Arrivals by LGU",
            "columns": ["LGU", "Visitors", "Reports"],
            "rows": [[r["lgu_name"], r["total_visitors"], r["report_count"]] for r in by_lgu],
        }
    return None


_FRIENDLY_ERROR = (
    "Sorry, I couldn't load that information right now. Please try again in a moment."
)


_ORIGIN_PROMPT_PHRASES = ("coming from", "you're from", "you are from", "where are you")


def _awaiting_route_origin(history: list[dict]) -> bool:
    """True if LARA's most recent reply looks like it just asked the user
    where they're traveling from (the route-clarification question from
    tourist prompt rule 9) — the only case where an otherwise-unrelated
    follow-up message should still be checked for a route answer.

    Scans backward for the most recent model/assistant turn rather than
    only checking history[-1] — the frontend pushes the current user
    message onto `history` before sending, so the last entry is always the
    user's own current message, not LARA's prior reply."""
    for turn in reversed(history or []):
        role = (turn.get("role") or "").lower()
        if role in ("model", "assistant", "lara"):
            text = (turn.get("content") or "").lower()
            return any(phrase in text for phrase in _ORIGIN_PROMPT_PHRASES)
    return False


def _detect_miss(
    intents: list[str],
    context: dict[str, Any],
    route: dict[str, Any] | None,
    is_route_query: bool,
    reply_text: str,
) -> str | None:
    """Deterministically flag a content gap worth logging for FAQ triage.
    Excludes arrival_analytics/decision_support (empty there is usually a
    role/scope gate working as intended, not a missing fact) and 'general'
    chit-chat (no keyword matched, not a knowledge gap)."""
    if is_route_query and route is None:
        return "route"
    for key in _MISS_INTENT_KEYS:
        if key in intents and context.get(key) == []:
            return key
    if _CANT_FIND_PHRASE in reply_text.lower():
        return "spots"
    return None


def chat(
    message: str,
    history: list[dict],
    scope: dict[str, Any],
) -> dict[str, Any]:
    """
    Main LARA chat function using google-genai package.
    `scope` must come from services.chatbot_scope.resolve_chat_scope() —
    never build it from client-submitted values.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "error": "GEMINI_API_KEY not configured."}

    message = (message or "").strip()
    if not message:
        return {"success": False, "error": "Message cannot be empty."}

    # The frontend pushes the user's current message onto `history` before
    # sending it, so the last entry is always a duplicate of `message`, not
    # a prior turn. Strip it here so every downstream use of `history`
    # (route resolution, origin-clarification detection, and the Gemini
    # history passed to start_chat) consistently means "prior turns only" —
    # otherwise the current message gets sent to Gemini twice (once via
    # start_chat's history, once via send_message).
    history = list(history or [])
    if (
        history
        and (history[-1].get("role") or "").lower() == "user"
        and (history[-1].get("content") or "").strip() == message
    ):
        history = history[:-1]

    role = scope.get("role") if scope.get("role") in _SYSTEM_PROMPTS else "tourist"

    cache_key = _cache_key(message, scope)
    cached = _RESPONSE_CACHE.get(cache_key)
    if cached:
        return {**cached, "cached": True}

    try:
        intents = classify_intent(message)
        context = build_context(intents, scope, message)
    except Exception:
        intents = []
        context = {}

    # Route intent may only be evident from earlier turns (e.g. LARA asked
    # "where are you coming from?" and this message is just the answer like
    # "Calamba"). Only fall back to scanning history for a route keyword
    # when LARA's own last reply looks like that clarifying question —
    # otherwise any unrelated follow-up within a few turns of an earlier
    # route question would get mislabeled as a route query too.
    route = None
    is_route_query = INTENT_ROUTE in intents
    if not is_route_query and _awaiting_route_origin(history):
        route_check_blob = "\n".join(
            [message] + [(h.get("content") or "") for h in (history or [])[-6:]]
        )
        is_route_query = INTENT_ROUTE in classify_intent(route_check_blob)
    if is_route_query:
        try:
            route = resolve_route(message, history)
        except Exception:
            route = None

    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)

        db_context_parts = [_LAGUNA_GENERAL_INFO.strip()]
        if route:
            db_context_parts.append(_fmt_route(route))
        db_context_parts.append(_format_context_text(context))
        db_context = "\n\n".join(p for p in db_context_parts if p)

        system_instruction = _SYSTEM_PROMPTS[role].format(
            shared_rules=_SHARED_RULES, db_context=db_context
        )

        model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
            system_instruction=system_instruction,
        )

        history_for_api = []
        for item in (history or [])[-8:]:
            g_role = "user" if item.get("role") == "user" else "model"
            content = (item.get("content") or "").strip()
            if content:
                history_for_api.append({"role": g_role, "parts": [content]})

        chat_session = model.start_chat(history=history_for_api)

        last_exc = None
        for attempt in range(2):
            try:
                response = chat_session.send_message(
                    message,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=512,
                        temperature=0.7,
                    ),
                )
                last_exc = None
                break
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if "500" in err_str and attempt == 0:
                    time.sleep(1.5)
                    chat_session = model.start_chat(history=history_for_api)
                    continue
                raise

        if last_exc:
            raise last_exc

        reply_text = (response.text or "").strip()

        if not reply_text:
            return {"success": False, "error": "No response from AI model."}

        try:
            cards = _build_cards(context, reply_text, route)
        except Exception:
            cards = None
        chart = _build_chart(context)
        table = _build_table(context)

        result = {
            "success": True,
            "reply": reply_text,
            "cards": cards,
            "table": table,
            "chart": chart,
            "route": route,
        }
        # Only cache standalone (first-message / no prior context) queries.
        # The cache key is message text only, but plenty of real follow-ups
        # ("tell me more about it", "how much does it cost") depend entirely
        # on that specific conversation's history for their correct answer —
        # caching those risks serving a completely wrong answer to an
        # unrelated conversation that happens to type the same short
        # follow-up. A context-free message's answer is safe to reuse
        # regardless of some other caller's history, so only the write side
        # needs this guard.
        if not is_route_query and not history:
            _RESPONSE_CACHE.set(cache_key, result)

        miss_intent = _detect_miss(intents, context, route, is_route_query, reply_text)
        if miss_intent:
            # Fire-and-forget: logging a miss must never delay or break the
            # actual chat response, so it runs off-thread and swallows its
            # own errors (see log_unanswered_query).
            threading.Thread(
                target=log_unanswered_query,
                args=(message,),
                kwargs={"intent": miss_intent, "role": scope.get("role")},
                daemon=True,
            ).start()

        return {**result, "cached": False}

    except Exception as exc:
        err_str = str(exc)
        is_quota_error = (
            isinstance(exc, _QUOTA_EXC_TYPES)
            or "429" in err_str
            or "quota" in err_str.lower()
            or "resource_exhausted" in err_str.lower()
            or "too many requests" in err_str.lower()
        )
        if is_quota_error:
            return {
                "success": False,
                "error": (
                    "LARA has reached its AI token/quota limit for now. "
                    "Please wait for the limit to reset before trying again."
                ),
                "quota_exceeded": True,
            }
        return {"success": False, "error": _FRIENDLY_ERROR}
