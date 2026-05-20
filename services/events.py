"""
Events / promotions from Supabase.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from services.supabase_client import get_supabase

EVENT_SELECT = "*, lgus(id, name)"

APPROVED = "approved"
EVENT_STATUSES = ("draft", "upcoming", "ongoing", "finished")
VISIBILITIES = ("public", "private", "featured")


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:80] or "event"


def _parse_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def list_events(
    *,
    lgu_id: int | None = None,
    approval_status: str | None = None,
    public_approved_only: bool = False,
    event_status: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = get_supabase().table("events").select(EVENT_SELECT)
    if public_approved_only:
        # Show all events that haven't been explicitly rejected.
        # LTCATO staff are the only publishers and events are auto-approved
        # on save, so filtering to 'rejected' exclusion is enough.
        query = query.neq("approval_status", "rejected")
    elif approval_status:
        query = query.eq("approval_status", approval_status)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    if event_status:
        query = query.eq("event_status", event_status)
    if category:
        query = query.eq("category", category)
    response = query.order("start_date", desc=True).limit(limit).execute()
    rows = response.data or []
    if public_approved_only:
        # Exclude private events from the public listing.
        rows = [e for e in rows if (e.get("visibility") or "public") != "private"]
    return rows


def get_event(event_id: int, *, public_only: bool = False) -> dict[str, Any] | None:
    try:
        query = get_supabase().table("events").select(EVENT_SELECT).eq("id", event_id)
        if public_only:
            query = query.neq("approval_status", "rejected")
        response = query.single().execute()
        event = response.data
        if event and public_only and (event.get("visibility") or "public") == "private":
            return None
        if event:
            event["exhibitors"] = list_event_exhibitors(event_id)
            try:
                ana = (
                    get_supabase()
                    .table("event_analytics")
                    .select("*")
                    .eq("event_id", event_id)
                    .limit(1)
                    .execute()
                )
                event["event_analytics"] = ana.data[0] if ana.data else {}
            except Exception:
                event["event_analytics"] = {}
        return event
    except Exception:
        return None


def list_event_exhibitors(event_id: int) -> list[dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table("event_exhibitors")
            .select("*, lgus(id, name)")
            .eq("event_id", event_id)
            .order("sort_order")
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def _filter_active_public_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep upcoming/ongoing events, ordered soonest first."""
    active = [e for e in rows if _compute_event_status(e) in ("upcoming", "ongoing")]
    active.sort(key=lambda e: (e.get("start_date") or "9999-12-31"))
    return active


def list_home_events(limit: int = 3) -> list[dict[str, Any]]:
    """Enriched upcoming/ongoing events for the home page."""
    raw = list_events(public_approved_only=True, limit=100)
    active = _filter_active_public_events(raw)
    return [enrich_event_for_display(e) for e in active[:limit]]


def list_lgu_public_events(lgu_id: int, limit: int = 4) -> list[dict[str, Any]]:
    """Enriched upcoming/ongoing events for an LGU detail page."""
    raw = list_events(lgu_id=lgu_id, public_approved_only=True, limit=50)
    active = _filter_active_public_events(raw)
    return [enrich_event_for_display(e) for e in active[:limit]]


def list_events_public(
    *,
    lgu_id: int | None = None,
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    events = list_events(
        lgu_id=lgu_id,
        public_approved_only=True,
        limit=200,
        category=category,
    )
    if status:
        events = [e for e in events if _compute_event_status(e) == status]
    if not q:
        return events
    term = q.strip().lower()
    return [
        e
        for e in events
        if term in (e.get("title") or "").lower()
        or term in (e.get("short_description") or e.get("description") or "").lower()
        or term in (e.get("full_description") or "").lower()
        or term in ((e.get("lgus") or {}).get("name") or "").lower()
        or term in (e.get("venue_name") or e.get("venue") or "").lower()
        or term in (e.get("tagline") or "").lower()
    ]


def get_event_lgu_name(event: dict[str, Any]) -> str:
    lgu = event.get("lgus")
    if isinstance(lgu, dict):
        return lgu.get("name") or "Laguna"
    return "Laguna"


def _compute_event_status(event: dict[str, Any]) -> str:
    explicit = (event.get("event_status") or "").lower()
    # Published lifecycle statuses are authoritative; draft/missing uses dates.
    if explicit in ("upcoming", "ongoing", "finished"):
        return explicit
    today = date.today()
    start_raw = event.get("start_date")
    end_raw = event.get("end_date")
    try:
        start = date.fromisoformat(str(start_raw)[:10]) if start_raw else None
        end = date.fromisoformat(str(end_raw)[:10]) if end_raw else start
    except ValueError:
        return "upcoming"
    if start and today < start:
        return "upcoming"
    if end and today > end:
        return "finished"
    if start and (not end or start <= today <= end):
        return "ongoing"
    return "upcoming"


def _parse_event_date(date_str: str | None) -> tuple[str, str]:
    if not date_str:
        return "TBA", "—"
    try:
        parts = str(date_str).split("-")
        if len(parts) >= 3:
            month_names = [
                "",
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            month = month_names[int(parts[1])]
            day = str(int(parts[2]))
            return month, day
    except (ValueError, IndexError):
        pass
    return "TBA", "—"


def build_event_gallery(event: dict[str, Any]) -> list[str]:
    images: list[str] = []
    for key in ("cover_image", "banner_image", "official_banner"):
        url = event.get(key)
        if url and url not in images:
            images.append(url)
    for url in event.get("gallery_images") or []:
        if url and url not in images:
            images.append(url)
    return images


def enrich_event_for_display(event: dict[str, Any]) -> dict[str, Any]:
    month, day = _parse_event_date(event.get("start_date"))
    status = _compute_event_status(event)
    category = (event.get("category") or "festival").lower()
    short = event.get("short_description") or event.get("description") or ""
    analytics = event.get("event_analytics")
    if isinstance(analytics, list) and analytics:
        analytics = analytics[0]
    if not isinstance(analytics, dict):
        analytics = {}

    return {
        **event,
        "image": event.get("cover_image")
        or event.get("banner_image")
        or event.get("official_banner")
        or "/static/images/kapitolyo.jpg",
        "municipality": get_event_lgu_name(event),
        "summary": short,
        "description_html": event.get("full_description") or short,
        "date_month": month,
        "date_day": day,
        "time": event.get("venue_name") or event.get("venue") or "Venue TBA",
        "status": status,
        "attendee_count": event.get("interested_count")
        or event.get("attendance_count")
        or 0,
        "going_count": event.get("going_count") or 0,
        "category": category,
        "date_label": event.get("start_date") or "Date TBA",
        "date_end_label": event.get("end_date"),
        "organizer": event.get("organizer") or "LTCATO / Provincial Tourism",
        "contact": event.get("contact_person") or "See event details",
        "admission": event.get("visibility", "public").title()
        if event.get("visibility")
        else "Public",
        "address": event.get("barangay") or get_event_lgu_name(event),
        "venue": event.get("venue_name") or event.get("venue") or "TBA",
        "tagline": event.get("tagline") or short,
        "views": analytics.get("views", 0),
        "gallery": build_event_gallery(event),
    }


def get_related_events(event: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    lgu_id = event.get("lgu_id")
    events = list_events(lgu_id=lgu_id, public_approved_only=True, limit=limit + 5)
    related = [
        enrich_event_for_display(e) for e in events if e.get("id") != event.get("id")
    ]
    return related[:limit]


def build_event_payload_from_form(form, files) -> dict[str, Any]:
    """Map Flask request form/files to events row."""
    title = _strip(form.get("title")) or ""
    if not title:
        raise ValueError("Event title is required.")

    slug = _strip(form.get("slug")) or _slugify(title)
    event_status = _strip(form.get("event_status")) or "draft"
    if event_status not in EVENT_STATUSES:
        event_status = "draft"
    visibility = _strip(form.get("visibility")) or "public"
    if visibility not in VISIBILITIES:
        visibility = "public"

    lgu_raw = _strip(form.get("lgu_id"))
    lgu_id = int(lgu_raw) if lgu_raw and lgu_raw.isdigit() else None

    short = _strip(form.get("short_description"))
    full_html = _strip(form.get("full_description"))

    payload: dict[str, Any] = {
        "title": title,
        "slug": slug,
        "short_description": short,
        "full_description": full_html,
        "description": short,
        "category": _strip(form.get("category")),
        "subcategory": _strip(form.get("subcategory")),
        "event_status": event_status,
        "visibility": visibility,
        "organizer": _strip(form.get("organizer")),
        "contact_person": _strip(form.get("contact_person")),
        "theme": _strip(form.get("theme")),
        "tagline": _strip(form.get("tagline")),
        "tourism_campaign_type": _strip(form.get("tourism_campaign_type")),
        "start_date": _strip(form.get("start_date")),
        "end_date": _strip(form.get("end_date")),
        "registration_deadline": _strip(form.get("registration_deadline")),
        "venue_name": _strip(form.get("venue_name")),
        "venue": _strip(form.get("venue_name")),
        "venue_type": _strip(form.get("venue_type")),
        "lgu_id": lgu_id,
        "barangay": _strip(form.get("barangay")),
        "latitude": _parse_float(form.get("latitude")),
        "longitude": _parse_float(form.get("longitude")),
        "map_pin": _strip(form.get("map_pin")),
        "virtual_event_link": _strip(form.get("virtual_event_link")),
        "overview": _strip(form.get("overview")),
        "historical_background": _strip(form.get("historical_background")),
        "significance": _strip(form.get("significance")),
        "cultural_importance": _strip(form.get("cultural_importance")),
        "tourism_impact": _strip(form.get("tourism_impact")),
        "expected_visitors": _parse_int(form.get("expected_visitors")),
        "economic_contribution": _strip(form.get("economic_contribution")),
        "tourism_office": _strip(form.get("tourism_office")),
        "pavilion_booth_no": _strip(form.get("pavilion_booth_no")),
        "pavilion_products": _strip(form.get("pavilion_products")),
        "featured_destination": _strip(form.get("featured_destination")),
        "representative": _strip(form.get("representative")),
        "approval_status": "approved",
    }

    from services.storage import upload_gallery_files, upload_optional_file

    cover = upload_optional_file(
        files.get("cover_image"), folder="events/covers", kind="image"
    )
    if cover:
        payload["cover_image"] = cover
        payload["banner_image"] = cover

    banner = upload_optional_file(
        files.get("official_banner"), folder="events/banners", kind="image"
    )
    if banner:
        payload["official_banner"] = banner
        # If no cover image was uploaded, use the official banner as the cover
        if not cover:
            payload["cover_image"] = banner
            payload["banner_image"] = banner

    logo = upload_optional_file(
        files.get("event_logo"), folder="events/logos", kind="image"
    )
    if logo:
        payload["event_logo"] = logo

    video = upload_optional_file(
        files.get("featured_cover_video"), folder="events/videos", kind="video"
    )
    if video:
        payload["featured_cover_video"] = video

    promo = upload_optional_file(
        files.get("promo_video"), folder="events/videos", kind="video"
    )
    if promo:
        payload["promo_video"] = promo

    drone = upload_optional_file(
        files.get("drone_footage"), folder="events/videos", kind="video"
    )
    if drone:
        payload["drone_footage"] = drone

    poster = upload_optional_file(
        files.get("poster_pdf"), folder="events/docs", kind="document"
    )
    if poster:
        payload["poster_pdf"] = poster

    brochure = upload_optional_file(
        files.get("brochure"), folder="events/docs", kind="document"
    )
    if brochure:
        payload["brochure"] = brochure

    gallery_files = files.getlist("gallery_images") if hasattr(files, "getlist") else []
    gallery_urls = upload_gallery_files(gallery_files)
    if gallery_urls:
        payload["gallery_images"] = gallery_urls

    social_files = files.getlist("social_assets") if hasattr(files, "getlist") else []
    social_urls = upload_gallery_files(social_files, folder="events/social")
    if social_urls:
        payload["social_assets"] = social_urls

    return payload


def create_event_from_request(form, files, *, created_by: str | None) -> dict[str, Any]:
    payload = build_event_payload_from_form(form, files)
    if created_by:
        payload["created_by"] = created_by

    response = get_supabase().table("events").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Event was not saved.")
    event = response.data[0]
    _save_exhibitors_from_form(event["id"], form)
    return event


def _save_exhibitors_from_form(event_id: int, form) -> None:
    rows: list[dict[str, Any]] = []
    names = form.getlist("exhibitor_business_name") if hasattr(form, "getlist") else []
    if not names:
        single = _strip(form.get("exhibitor_business_name"))
        if single:
            names = [single]
    owners = (
        form.getlist("exhibitor_owner")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_owner")]
    )
    categories = (
        form.getlist("exhibitor_category")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_category")]
    )
    products = (
        form.getlist("exhibitor_products")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_products")]
    )
    booths = (
        form.getlist("exhibitor_booth_number")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_booth_number")]
    )
    fb_pages = (
        form.getlist("exhibitor_fb_page")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_fb_page")]
    )
    websites = (
        form.getlist("exhibitor_website")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_website")]
    )
    lgu_ids = (
        form.getlist("exhibitor_lgu_id")
        if hasattr(form, "getlist")
        else [form.get("exhibitor_lgu_id")]
    )

    for i, business_name in enumerate(names):
        name = _strip(business_name)
        if not name:
            continue
        lgu_raw = lgu_ids[i] if i < len(lgu_ids) else None
        lgu_id = int(lgu_raw) if lgu_raw and str(lgu_raw).isdigit() else None
        rows.append(
            {
                "event_id": event_id,
                "business_name": name,
                "owner_name": _strip(owners[i] if i < len(owners) else None),
                "category": _strip(categories[i] if i < len(categories) else None),
                "products": _strip(products[i] if i < len(products) else None),
                "booth_number": _strip(booths[i] if i < len(booths) else None),
                "fb_page": _strip(fb_pages[i] if i < len(fb_pages) else None),
                "website": _strip(websites[i] if i < len(websites) else None),
                "lgu_id": lgu_id,
                "sort_order": i,
            }
        )

    if rows:
        get_supabase().table("event_exhibitors").insert(rows).execute()
