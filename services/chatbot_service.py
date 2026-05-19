"""
LARA Chatbot Service — Gemini AI powered (google-genai package).
Role-aware tourism assistant for Laguna Province.

Install: pip install google-genai
Model: gemini-2.5-flash (free tier: 20 req/day — upgrade at https://ai.google.dev)

Free tier limit: 20 requests/day. Quota resets at midnight UTC.
For production, enable billing at https://ai.google.dev to get 1,500+ req/day.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from services.supabase_client import get_supabase

# ── Simple response cache to save quota ───────────────────────────────────
# Exact same message within the same day → return cached reply (saves quota)
_RESPONSE_CACHE: dict[str, tuple[str, float]] = {}  # key → (reply, timestamp)
_CACHE_TTL = 3600  # 1 hour


def _cache_key(message: str, role: str) -> str:
    return hashlib.md5(f"{role}:{message.lower().strip()}".encode()).hexdigest()


def _get_cached(message: str, role: str) -> str | None:
    key = _cache_key(message, role)
    cached = _RESPONSE_CACHE.get(key)
    if cached and (time.time() - cached[1]) < _CACHE_TTL:
        return cached[0]
    return None


def _set_cached(message: str, role: str, reply: str) -> None:
    key = _cache_key(message, role)
    _RESPONSE_CACHE[key] = (reply, time.time())


# ── System prompts per role ────────────────────────────────────────────────
_SYSTEM_PROMPTS = {
    "tourist": """You are LARA (Laguna AI Tourism Assistant), the official AI guide of LTCATO — Laguna Tourism Culture Arts and Trade Office.
You are extremely welcoming, polite, enthusiastic, and knowledgeable about Laguna's culture, municipalities, and tourist spots.

IMPORTANT RULES:
1. You were created and programmed by the 'LTCATO Development Team' (Laguna Tourism Culture Arts and Trade Office). Special Mention: Lawrence Celis. If asked who made you, proudly state this.
2. ONLY provide information about tourist spots that are listed in the database below.
3. The MUNICIPALITY is the primary location identifier — not the address. A spot belongs to the municipality shown in the database, regardless of its stated address.
4. If someone asks about a spot NOT in the database, respond: "I can't find it in my database."
5. Keep all responses SHORT and CONCISE (2–3 sentences maximum).
6. Be friendly and helpful about Laguna's culture and tourism.
7. Answer in the language the user uses (English or Filipino or Taglish).
8. If the user asks for directions, provide a general description of how to get there from the city center of the municipality, but do NOT provide turn-by-turn directions.
9. If the user asks for directions, ask where they are from and where they want to go, then provide an estimated time and distance based on typical routes — but do NOT provide specific routes or turn-by-turn directions.

{db_context}""",
    "lgu_admin": """You are LARA, the LTCATO AI management assistant for LGU tourism officers in Laguna Province.
You help LGU admins with:
- Tourist spot approval workflow (pending_lgu → pending_ltcato → approved)
- Guidance on submitting and reviewing arrival reports
- Understanding their municipality's tourism data and best practices

RULES:
1. Be professional. Reference specific data from the database when relevant.
2. Answer in English or Filipino as the user prefers.

{db_context}""",
    "ltcato_staff": """You are LARA, the LTCATO Provincial Tourism AI assistant for LTCATO staff.
You assist with analytics, spot/event approval workflows, visitor trends, and decision support data.

RULES:
1. Provide data-driven insights using actual numbers from the database.
2. Be professional and concise.

{db_context}""",
    "super_admin": """You are LARA, the LTCATO AI system assistant for the Super Administrator.
You have full access to all Laguna Province tourism data.

{db_context}""",
    "establishment_owner": """You are LARA, the LTCATO AI assistant for tourism establishment owners.
You help with arrival reports, spot registration, and improving the establishment listing.

RULES:
1. Focus on practical, step-by-step guidance.
2. Be encouraging and supportive.

{db_context}""",
}


def _build_db_context(role: str, lgu_id: int | None = None) -> str:
    """Build a database context string for the system prompt."""
    parts: list[str] = []

    # Approved tourist spots grouped by LGU
    try:
        q = (
            get_supabase()
            .table("tourist_spots")
            .select("name, lgus(name)")
            .eq("approval_status", "approved")
            .limit(60)
        )
        if lgu_id and role == "lgu_admin":
            q = q.eq("lgu_id", lgu_id)
        spots = q.execute().data or []
        if spots:
            grouped: dict[str, list[str]] = {}
            for s in spots:
                lgu_name = (s.get("lgus") or {}).get("name", "Unknown LGU")
                grouped.setdefault(lgu_name, []).append(s["name"])
            parts.append("\n=== TOURIST SPOTS BY LGU ===")
            for lgu_name, names in sorted(grouped.items()):
                parts.append(f"\n{lgu_name}:")
                for n in names:
                    parts.append(f"  - {n}")
    except Exception:
        pass

    # Upcoming and ongoing events
    try:
        from services.events import list_events, _compute_event_status

        raw = list_events(public_approved_only=True, limit=50)
        events = [e for e in raw if _compute_event_status(e) in ("upcoming", "ongoing")][:20]
        if events:
            parts.append("\n\n=== UPCOMING / ONGOING EVENTS ===")
            for e in events:
                lgu_n = (e.get("lgus") or {}).get("name", "")
                dates = (
                    f" ({e.get('start_date', '')} – {e.get('end_date', '')})"
                    if e.get("start_date")
                    else ""
                )
                parts.append(f"  - {e['title']}{dates} — {lgu_n}")
    except Exception:
        pass

    # LGUs list
    try:
        lgus = get_supabase().table("lgus").select("name, type").execute().data or []
        if lgus:
            cities = [l["name"] for l in lgus if l.get("type") == "city"]
            munis = [l["name"] for l in lgus if l.get("type") != "city"]
            parts.append("\n\n=== LAGUNA LGUs ===")
            if cities:
                parts.append(f"Cities: {', '.join(cities)}")
            if munis:
                parts.append(f"Municipalities: {', '.join(munis)}")
    except Exception:
        pass

    # Approved FAQ knowledge base
    try:
        faq = (
            get_supabase()
            .table("chatbot_knowledge")
            .select("question, answer")
            .eq("approval_status", "approved")
            .limit(20)
            .execute()
            .data
            or []
        )
        if faq:
            parts.append("\n\n=== FAQ KNOWLEDGE BASE ===")
            for f in faq:
                parts.append(f"Q: {f.get('question', '')}\nA: {f.get('answer', '')}")
    except Exception:
        pass

    return "\n".join(parts) if parts else "\n(No data available)"


def chat(
    message: str,
    history: list[dict],
    role: str = "tourist",
    lgu_id: int | None = None,
) -> dict[str, Any]:
    """
    Main LARA chat function using google-genai package.
    Includes response caching to preserve daily quota.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "error": "GEMINI_API_KEY not configured."}

    message = (message or "").strip()
    if not message:
        return {"success": False, "error": "Message cannot be empty."}

    normalized_role = role if role in _SYSTEM_PROMPTS else "tourist"

    # Check cache first (saves quota for repeated questions)
    cached = _get_cached(message, normalized_role)
    if cached:
        return {"success": True, "reply": cached, "cached": True}

    try:
        from google import genai as google_genai  # type: ignore
        from google.genai import types as genai_types  # type: ignore

        client = google_genai.Client(api_key=api_key)

        db_context = _build_db_context(normalized_role, lgu_id)
        system_instruction = _SYSTEM_PROMPTS[normalized_role].format(
            db_context=db_context
        )

        # Build conversation contents for the API
        contents: list = []
        for item in (history or [])[-8:]:  # Last 8 turns to save tokens
            g_role = "user" if item.get("role") == "user" else "model"
            content = (item.get("content") or "").strip()
            if content:
                contents.append({"role": g_role, "parts": [{"text": content}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=512,
                temperature=0.7,
            ),
        )

        reply_text = ""
        if response and response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                reply_text = "".join(
                    p.text for p in candidate.content.parts if hasattr(p, "text")
                ).strip()

        if reply_text:
            _set_cached(message, normalized_role, reply_text)
            return {"success": True, "reply": reply_text}
        else:
            return {"success": False, "error": "No response from AI model."}

    except Exception as exc:
        err_str = str(exc)
        if (
            "429" in err_str
            or "quota" in err_str.lower()
            or "RESOURCE_EXHAUSTED" in err_str
        ):
            return {
                "success": False,
                "error": (
                    "LARA's daily quota (20 free requests) has been reached. "
                    "The quota resets at midnight UTC. "
                    "To get unlimited access, enable billing at https://ai.google.dev"
                ),
            }
        return {"success": False, "error": f"AI error: {str(exc)[:200]}"}
