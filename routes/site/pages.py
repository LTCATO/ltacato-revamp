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


@public_bp.route("/api/lara/chat", methods=["POST"])
def lara_chat():
    """LARA AI chatbot endpoint — role-aware, Gemini-powered."""
    from flask import jsonify
    from flask import request as _req

    try:
        data = _req.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        history = data.get("history", [])
        role = data.get("role", "tourist")
        lgu_id = data.get("lgu_id")

        # Use logged-in user's role if available
        try:
            from services.dashboard_auth import get_current_dashboard_user
            from services.tourist_auth import get_current_tourist

            db_user = get_current_dashboard_user()
            if db_user:
                role = db_user.get("role", "tourist")
                lgu_id = db_user.get("lgu_id") or lgu_id
        except Exception:
            pass

        from services.chatbot_service import chat

        result = chat(message=message, history=history, role=role, lgu_id=lgu_id)
        return jsonify(result), 200 if result.get("success") else 500

    except Exception as exc:
        from flask import jsonify

        return jsonify({"success": False, "error": str(exc)}), 500
