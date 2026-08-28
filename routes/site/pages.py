from flask import Blueprint, render_template

from services.citizen_charter import ABOUT_LAGUNA, CHARTER_SECTIONS
from services.governor import GOVERNOR, GOVERNOR_TEASER

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    from services.home_service import get_home_events, get_trending_spots
    from utils.jinja_helpers import normalize_image_url

    events = get_home_events(limit=3)
    for event in events:
        img = normalize_image_url(event.get("image"))
        event["image"] = img or event.get("image")

    trending = get_trending_spots(limit=3)
    return render_template(
        "views/site/home.html",
        home_events=events,
        trending_spots=trending,
    )


@public_bp.route("/about")
def about():
    return render_template(
        "views/site/about.html",
        about=ABOUT_LAGUNA,
        charter_sections=CHARTER_SECTIONS,
        governor_teaser=GOVERNOR_TEASER,
    )


@public_bp.route("/about/governor")
def governor():
    return render_template("views/site/governor.html", governor=GOVERNOR)


@public_bp.route("/terms-use")
def terms_use():
    return render_template("views/site/terms_use.html")


@public_bp.route("/privacy-policy")
def privacy_policy():
    return render_template("views/site/privacy_policy.html")


@public_bp.route("/api/lara/chat", methods=["POST"])
def lara_chat():
    """LARA AI chatbot endpoint — role-aware, intent-scoped, Gemini-powered."""
    from flask import jsonify
    from flask import request as _req

    try:
        data = _req.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        history = data.get("history", [])

        # Permission scope is resolved entirely server-side from the
        # session — role/lgu_id are never taken from the request body.
        from services.chatbot_rate_limit import check_rate_limit
        from services.chatbot_scope import resolve_chat_scope
        from services.chatbot_service import chat

        scope = resolve_chat_scope()

        client_ip = (_req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                     or _req.remote_addr)
        if not check_rate_limit(scope, client_ip):
            return jsonify(
                {
                    "success": False,
                    "error": (
                        "You're sending messages too quickly — please wait a "
                        "few minutes before asking LARA more questions."
                    ),
                    "rate_limited": True,
                }
            ), 429

        result = chat(message=message, history=history, scope=scope)
        return jsonify(result), 200 if result.get("success") else 500

    except Exception:
        from flask import jsonify

        return jsonify(
            {"success": False, "error": "LARA is temporarily unavailable. Please try again."}
        ), 500
