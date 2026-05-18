import logging

from flask import Blueprint, abort, jsonify, render_template, request

from services.spot_engagement import (
    get_spot_engagement_counts,
    get_user_spot_engagement,
    get_user_spot_feedback,
    toggle_spot_engagement,
)
from services.spots import (
    PER_PAGE,
    get_categories,
    get_lgus,
    get_related_spots,
    get_spot,
    get_spot_feedbacks,
    list_spots,
    spot_lgu_name,
)
from services.supabase_client import get_supabase
from services.tourist_auth import get_current_tourist
from utils.jinja_helpers import ensure_list, normalize_image_url

logger = logging.getLogger(__name__)

spots_bp = Blueprint("spots", __name__)


# ---------------------------------------------------------------------------
# Public listing
# ---------------------------------------------------------------------------


@spots_bp.route("/spots")
def spots_list():
    category_raw = request.args.get("category") or None
    category_id = int(category_raw) if category_raw and category_raw.isdigit() else None
    lgu_raw = request.args.get("municipality") or request.args.get("lgu")
    lgu_id = int(lgu_raw) if lgu_raw and str(lgu_raw).isdigit() else None
    q = request.args.get("q") or None
    sort = request.args.get("sort", "name")
    page = request.args.get("page", 1, type=int)

    if sort not in ("name", "rating", "reviews"):
        sort = "name"

    try:
        spots, total = list_spots(
            category_id=category_id,
            lgu_id=lgu_id,
            q=q,
            sort=sort,
            page=page,
        )
        municipalities = get_lgus()
        categories = get_categories()
    except Exception as exc:
        logger.exception("Failed to load spots list: %s", exc)
        spots, total = [], 0
        municipalities = []
        categories = []

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE) if total else 1
    if page > total_pages:
        page = total_pages

    return render_template(
        "views/site/spots/list.html",
        spots=spots,
        total=total,
        page=page,
        total_pages=total_pages,
        per_page=PER_PAGE,
        municipalities=municipalities,
        categories=categories,
        active_category=category_id,
        active_municipality=lgu_id,
        active_q=q or "",
        active_sort=sort,
    )


# ---------------------------------------------------------------------------
# Spot detail
# ---------------------------------------------------------------------------


@spots_bp.route("/spots/<int:spot_id>")
def spot_detail(spot_id: int):
    try:
        spot = get_spot(spot_id)
    except Exception:
        spot = None

    if not spot:
        abort(404)

    try:
        feedbacks = get_spot_feedbacks(spot_id)
        related = get_related_spots(spot)
    except Exception:
        feedbacks = []
        related = []

    tourist = get_current_tourist()
    user_engagement = None
    user_feedback = None
    try:
        if tourist:
            user_engagement = get_user_spot_engagement(tourist["id"], spot_id)
            user_feedback = get_user_spot_feedback(tourist["id"], spot_id)
    except Exception as exc:
        logger.warning("Failed to load spot engagement: %s", exc)

    spot_like_count = 0
    spot_bookmark_count = 0
    try:
        counts = get_spot_engagement_counts(spot_id)
        spot_like_count = counts["like_count"]
        spot_bookmark_count = counts["bookmark_count"]
    except Exception as exc:
        logger.warning("Failed to load spot engagement counts: %s", exc)

    municipality = spot.get("lgus") or {}
    gallery = [
        normalize_image_url(url) for url in ensure_list(spot.get("gallery_images"))
    ]
    gallery = [url for url in gallery if url]
    main_image = normalize_image_url(spot.get("main_image_url"))
    if main_image and main_image not in gallery:
        gallery.insert(0, main_image)
    elif not gallery and main_image:
        gallery = [main_image]

    return render_template(
        "views/site/spots/detail.html",
        spot=spot,
        municipality=municipality,
        lgu_name=spot_lgu_name(spot),
        feedbacks=feedbacks,
        related=related,
        gallery=gallery,
        user_engagement=user_engagement,
        user_feedback=user_feedback,
        spot_like_count=spot_like_count,
        spot_bookmark_count=spot_bookmark_count,
    )


# ---------------------------------------------------------------------------
# Engagement toggle (like / bookmark)
# ---------------------------------------------------------------------------


@spots_bp.route("/spots/<int:spot_id>/engage", methods=["POST"])
def spot_engage(spot_id: int):
    tourist = get_current_tourist()
    if not tourist:
        return jsonify({"error": "login_required"}), 401

    eng_type = request.json.get("type") if request.is_json else request.form.get("type")
    if eng_type not in ("like", "bookmark"):
        return jsonify({"error": "invalid_type"}), 400

    try:
        active = toggle_spot_engagement(tourist["id"], spot_id, eng_type)
    except Exception as exc:
        logger.exception("spot_engage error: %s", exc)
        return jsonify({"error": "server_error"}), 500

    return jsonify({"active": active})


# ---------------------------------------------------------------------------
# Spot feedback submission (rating + comment, once per tourist)
# ---------------------------------------------------------------------------


@spots_bp.route("/spots/<int:spot_id>/feedback", methods=["POST"])
def spot_feedback(spot_id: int):
    tourist = get_current_tourist()
    if not tourist:
        return jsonify({"error": "login_required"}), 401

    rating = request.form.get("rating", type=int)
    comment = (request.form.get("comment") or "").strip()
    suggestions = (request.form.get("suggestions") or "").strip()

    if not rating or rating < 1 or rating > 5:
        return jsonify({"error": "invalid_rating"}), 400

    existing = get_user_spot_feedback(tourist["id"], spot_id)
    if existing:
        return jsonify({"error": "already_submitted"}), 409

    guest_name = tourist.get("name") or "Visitor"

    try:
        sb = get_supabase()
        sb.table("feedbacks").insert(
            {
                "tourist_spot_id": spot_id,
                "tourist_id": tourist["id"],
                "guest_name": guest_name,
                "rating": rating,
                "comments": comment or None,
                "suggestions": suggestions or None,
                "source": "website",
            }
        ).execute()

        # Recompute running average and review count on the spots row
        rows = (
            sb.table("feedbacks")
            .select("rating")
            .eq("tourist_spot_id", spot_id)
            .execute()
        ).data or []
        rated = [r for r in rows if r.get("rating")]
        if rated:
            avg = round(sum(r["rating"] for r in rated) / len(rated), 2)
            sb.table("tourist_spots").update(
                {
                    "rating": avg,
                    "reviews_count": len(rated),
                }
            ).eq("id", spot_id).execute()
    except Exception as exc:
        logger.exception("spot_feedback error: %s", exc)
        return jsonify({"error": "server_error"}), 500

    return jsonify({"ok": True})
