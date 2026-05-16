from flask import Blueprint, abort, render_template, request

from services.spots import (
    PER_PAGE,
    get_categories,
    get_municipalities,
    get_related_spots,
    get_spot,
    get_spot_feedbacks,
    list_spots,
)
from utils.jinja_helpers import ensure_list, normalize_image_url

spots_bp = Blueprint("spots", __name__)


@spots_bp.route("/spots")
def spots_list():
    category = request.args.get("category") or None
    municipality_raw = request.args.get("municipality")
    municipality_id = int(municipality_raw) if municipality_raw and municipality_raw.isdigit() else None
    q = request.args.get("q") or None
    sort = request.args.get("sort", "name")
    page = request.args.get("page", 1, type=int)

    if sort not in ("name", "rating", "reviews"):
        sort = "name"

    try:
        spots, total = list_spots(
            category=category,
            municipality_id=municipality_id,
            q=q,
            sort=sort,
            page=page,
        )
        municipalities = get_municipalities()
        categories = get_categories()
    except Exception:
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
        active_category=category,
        active_municipality=municipality_id,
        active_q=q or "",
        active_sort=sort,
    )


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

    municipality = spot.get("municipalities") or {}
    gallery = [normalize_image_url(url) for url in ensure_list(spot.get("gallery_images"))]
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
        feedbacks=feedbacks,
        related=related,
        gallery=gallery,
    )
