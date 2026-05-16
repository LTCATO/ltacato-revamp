from flask import Blueprint, abort, render_template, request

from services.events_placeholder import (
    get_categories,
    get_event,
    get_municipalities,
    get_related_events,
    list_events,
)

events_bp = Blueprint("events", __name__)


@events_bp.route("/events")
def events_list():
    category = request.args.get("category") or None
    municipality = request.args.get("municipality") or None
    q = request.args.get("q") or None

    events = list_events(category=category, municipality=municipality, q=q)

    return render_template(
        "views/public/events/list.html",
        events=events,
        total=len(events),
        categories=get_categories(),
        municipalities=get_municipalities(),
        active_category=category,
        active_municipality=municipality,
        active_q=q or "",
    )


@events_bp.route("/events/<int:event_id>")
def event_detail(event_id: int):
    event = get_event(event_id)
    if not event:
        abort(404)

    related = get_related_events(event)
    gallery = [event["image"], *(event.get("gallery") or [])]
    gallery = [url for url in gallery if url]

    return render_template(
        "views/public/events/detail.html",
        event=event,
        related=related,
        gallery=gallery,
    )
