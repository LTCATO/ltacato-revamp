from flask import Blueprint, abort, render_template, request

from services.events import (
    enrich_event_for_display,
    get_event,
    get_related_events,
    list_events_public,
)
from services.lgus import list_lgus_simple
from utils.jinja_helpers import normalize_image_url

events_bp = Blueprint("events", __name__)


@events_bp.route("/events")
def events_list():
    lgu_raw = request.args.get("municipality") or request.args.get("lgu")
    lgu_id = int(lgu_raw) if lgu_raw and str(lgu_raw).isdigit() else None
    q = request.args.get("q") or None

    try:
        raw_events = list_events_public(lgu_id=lgu_id, q=q)
        events = [enrich_event_for_display(e) for e in raw_events]
        lgus = list_lgus_simple()
    except Exception:
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
        active_category=None,
        active_municipality=lgu_id,
        active_q=q or "",
    )


@events_bp.route("/events/<int:event_id>")
def event_detail(event_id: int):
    raw = get_event(event_id, public_only=True)
    if not raw:
        abort(404)

    event = enrich_event_for_display(raw)
    img = normalize_image_url(event.get("banner_image") or event.get("image"))
    gallery = [url for url in [img] if url]
    related = get_related_events(raw)

    return render_template(
        "views/site/events/detail.html",
        event=event,
        related=related,
        gallery=gallery,
    )
