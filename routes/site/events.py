import logging

from flask import Blueprint, abort, jsonify, render_template, request

from services.event_analytics import record_event_view
from services.event_engagement import (
    get_event_feedback,
    get_user_event_engagement,
    list_event_feedbacks,
    submit_event_feedback,
    toggle_event_engagement,
)
from services.events import (
    enrich_event_for_display,
    get_event,
    get_related_events,
    list_events_public,
)
from services.lgus import list_lgus_simple
from services.tourist_auth import get_current_tourist
from utils.jinja_helpers import normalize_image_url

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__)


# ---------------------------------------------------------------------------
# Public listing
# ---------------------------------------------------------------------------


@events_bp.route("/events")
def events_list():
    lgu_raw = request.args.get("municipality") or request.args.get("lgu")
    lgu_id = int(lgu_raw) if lgu_raw and str(lgu_raw).isdigit() else None
    q = request.args.get("q") or None
    status = request.args.get("status") or None
    category = request.args.get("category") or None

    try:
        raw_events = list_events_public(
            lgu_id=lgu_id, q=q, status=status, category=category
        )
        events = [enrich_event_for_display(e) for e in raw_events]
        lgus = list_lgus_simple()
    except Exception as exc:
        logger.exception("Failed to load events list: %s", exc)
        events = []
        lgus = []

    for event in events:
        img = normalize_image_url(event.get("image"))
        event["image"] = img or event.get("image")

    return render_template(
        "views/site/events/list.html",
        events=events,
        total=len(events),
        categories=[],
        municipalities=lgus,
        active_category=category,
        active_municipality=lgu_id,
        active_q=q or "",
        active_status=status or "",
    )


# ---------------------------------------------------------------------------
# Event detail
# ---------------------------------------------------------------------------


@events_bp.route("/events/<int:event_id>")
def event_detail(event_id: int):
    record_event_view(event_id)
    raw = get_event(event_id, public_only=True)
    if not raw:
        abort(404)

    event = enrich_event_for_display(raw)
    gallery: list[str] = []
    for url in event.get("gallery") or []:
        nu = normalize_image_url(url)
        if nu:
            gallery.append(nu)
    if not gallery:
        fallback = normalize_image_url(event.get("image")) or event.get("image")
        gallery = [fallback] if fallback else []

    related = get_related_events(raw)

    tourist = get_current_tourist()
    user_engagement = None
    user_feedback = None
    event_feedbacks = []
    try:
        event_feedbacks = list_event_feedbacks(event_id)
        if tourist:
            user_engagement = get_user_event_engagement(tourist["id"], event_id)
            user_feedback = get_event_feedback(tourist["id"], event_id)
    except Exception as exc:
        logger.warning("Failed to load event engagement: %s", exc)

    return render_template(
        "views/site/events/detail.html",
        event=event,
        related=related,
        gallery=gallery,
        user_engagement=user_engagement,
        user_feedback=user_feedback,
        event_feedbacks=event_feedbacks,
    )


# ---------------------------------------------------------------------------
# Engagement toggle (like / bookmark)
# ---------------------------------------------------------------------------


@events_bp.route("/events/<int:event_id>/engage", methods=["POST"])
def event_engage(event_id: int):
    tourist = get_current_tourist()
    if not tourist:
        return jsonify({"error": "login_required"}), 401

    eng_type = request.json.get("type") if request.is_json else request.form.get("type")
    if eng_type not in ("like", "bookmark"):
        return jsonify({"error": "invalid_type"}), 400

    try:
        active = toggle_event_engagement(tourist["id"], event_id, eng_type)
    except Exception as exc:
        logger.exception("event_engage error: %s", exc)
        return jsonify({"error": "server_error"}), 500

    return jsonify({"active": active})


# ---------------------------------------------------------------------------
# Feedback submission (rating + comment, once per tourist)
# ---------------------------------------------------------------------------


@events_bp.route("/events/<int:event_id>/feedback", methods=["POST"])
def event_feedback(event_id: int):
    tourist = get_current_tourist()
    if not tourist:
        return jsonify({"error": "login_required"}), 401

    rating = request.form.get("rating", type=int)
    comment = (request.form.get("comment") or "").strip()

    if not rating or rating < 1 or rating > 5:
        return jsonify({"error": "invalid_rating"}), 400

    try:
        ok = submit_event_feedback(tourist["id"], event_id, rating, comment)
    except Exception as exc:
        logger.exception("event_feedback error: %s", exc)
        return jsonify({"error": "server_error"}), 500

    if not ok:
        return jsonify({"error": "already_submitted"}), 409

    return jsonify({"ok": True})
