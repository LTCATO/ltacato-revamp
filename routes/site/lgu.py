import logging

from flask import Blueprint, abort, render_template, request

from services.events import list_lgu_public_events
from services.lgus import get_lgu, get_lgu_spots, get_related_lgus, list_lgus
from utils.jinja_helpers import normalize_image_url

logger = logging.getLogger(__name__)

lgu_bp = Blueprint("lgu", __name__)


@lgu_bp.route("/lgu")
def lgu_list():
    type_filter = request.args.get("type") or None
    if type_filter not in (None, "city", "municipality"):
        type_filter = None
    q = request.args.get("q") or None

    try:
        lgus, summary = list_lgus(type_filter=type_filter, q=q)
    except Exception as exc:
        logger.exception("Failed to load LGU list: %s", exc)
        lgus, summary = (
            [],
            {
                "total": 0,
                "cities": 0,
                "municipalities": 0,
                "with_spots": 0,
            },
        )

    cities = [m for m in lgus if m["type_normalized"] == "city"]
    towns = [m for m in lgus if m["type_normalized"] == "municipality"]

    return render_template(
        "views/site/lgu/list.html",
        municipalities=lgus,
        cities=cities,
        towns=towns,
        summary=summary,
        active_type=type_filter or "",
        active_q=q or "",
    )


@lgu_bp.route("/lgu/<int:lgu_id>")
def lgu_detail(lgu_id: int):
    try:
        municipality = get_lgu(lgu_id)
    except Exception:
        municipality = None

    if not municipality:
        abort(404)

    try:
        spots = get_lgu_spots(lgu_id)
        related = get_related_lgus(municipality)
        events = list_lgu_public_events(lgu_id, limit=4)
    except Exception:
        spots = []
        related = []
        events = []

    for event in events:
        img = normalize_image_url(event.get("image"))
        event["image"] = img or event.get("image")

    lat = municipality.get("latitude")
    lng = municipality.get("longitude")
    maps_url = None
    if lat is not None and lng is not None:
        maps_url = f"https://www.google.com/maps?q={lat},{lng}"

    return render_template(
        "views/site/lgu/detail.html",
        municipality=municipality,
        spots=spots,
        events=events,
        related=related,
        spot_count=len(spots),
        maps_url=maps_url,
    )
