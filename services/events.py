"""
Events / promotions from Supabase.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

# pyrefly: ignore [missing-import]
from postgrest.exceptions import APIError

from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# PostgREST's code for ".single() matched zero rows" — the only case that
# genuinely means "this event doesn't exist". Any other error (timeout,
# connection reset, etc.) is a real failure and shouldn't be logged as if
# it were a routine 404.
_NO_ROWS_CODE = "PGRST116"

EVENT_SELECT = "*, lgus(id, name)"

APPROVED = "approved"
EVENT_STATUSES = ("draft", "upcoming", "ongoing", "finished")
# "featured" used to be offered here but nothing in the app ever branched on
# it — actual featuring is the separate paid request_event_featured() /
# review_event_featured() workflow below. Dropped to stop staff from
# picking it and believing it features the event.
VISIBILITIES = ("public", "private")


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
        # LGU-submitted events start 'pending' and must not appear publicly
        # until an LTCATO staffer approves them.
        query = query.eq("approval_status", "approved")
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
            query = query.eq("approval_status", "approved")
        response = query.single().execute()
        event = response.data
        if event and public_only and (event.get("visibility") or "public") == "private":
            return None
        if event and public_only and _compute_event_status(event) == "draft":
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
                logger.exception("Failed to fetch analytics for event %s", event_id)
                event["event_analytics"] = {}
        return event
    except APIError as exc:
        if exc.code != _NO_ROWS_CODE:
            logger.exception("Failed to fetch event %s", event_id)
        return None
    except Exception:
        logger.exception("Failed to fetch event %s", event_id)
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
        logger.exception("Failed to fetch exhibitors for event %s", event_id)
        return []


def _filter_active_public_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep upcoming/ongoing events, currently-featured first, then soonest first."""
    active = [e for e in rows if _compute_event_status(e) in ("upcoming", "ongoing")]
    active.sort(
        key=lambda e: (not is_event_currently_featured(e), e.get("start_date") or "9999-12-31")
    )
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
    # Drafts are never public regardless of which status filter (if any) is
    # selected — get_event() enforces the same exclusion on the detail page,
    # so a draft slipping through here would list but 404 on click.
    events = [e for e in events if _compute_event_status(e) != "draft"]
    if status:
        events = [e for e in events if _compute_event_status(e) == status]
    if q:
        term = q.strip().lower()
        events = [
            e
            for e in events
            if term in (e.get("title") or "").lower()
            or term in (e.get("short_description") or e.get("description") or "").lower()
            or term in (e.get("full_description") or "").lower()
            or term in ((e.get("lgus") or {}).get("name") or "").lower()
            or term in (e.get("venue_name") or e.get("venue") or "").lower()
            or term in (e.get("tagline") or "").lower()
        ]
    events.sort(key=lambda e: not is_event_currently_featured(e))
    return events


def get_event_lgu_name(event: dict[str, Any]) -> str:
    lgu = event.get("lgus")
    if isinstance(lgu, dict):
        return lgu.get("name") or "Laguna"
    return "Laguna"


def _compute_event_status(event: dict[str, Any]) -> str:
    explicit = (event.get("event_status") or "").lower()
    # Draft is a manual editorial state, not derivable from dates.
    if explicit == "draft":
        return "draft"
    today = date.today()
    start_raw = event.get("start_date")
    end_raw = event.get("end_date")
    try:
        start = date.fromisoformat(str(start_raw)[:10]) if start_raw else None
        end = date.fromisoformat(str(end_raw)[:10]) if end_raw else start
    except ValueError:
        start = end = None
    # Dates are authoritative whenever available, so a stale manual status
    # (e.g. "finished" left over after an event was rescheduled) can't hide
    # an event whose actual dates are upcoming/ongoing.
    if start or end:
        if start and today < start:
            return "upcoming"
        if end and today > end:
            return "finished"
        if start and (not end or start <= today <= end):
            return "ongoing"
    if explicit in ("upcoming", "ongoing", "finished"):
        return explicit
    # No usable dates and no explicit status: treat as draft rather than
    # letting it sit on public listings as "upcoming" forever. This hides
    # any legacy/imported row with a null or corrupt start_date that used
    # to render as "upcoming" — logged so such rows are findable rather
    # than silently disappearing from the public site.
    if event.get("id") is not None:
        logger.warning(
            "Event %s has no usable dates and no explicit status; treating as draft",
            event.get("id"),
        )
    return "draft"


def is_event_currently_featured(event: dict[str, Any]) -> bool:
    """Featured is a computed window, not a permanent flag: it only shows
    from the event's start date through 5 days after it ends, and only
    once a Featured request has been approved."""
    if (event.get("featured_status") or "none") != "approved":
        return False
    start_raw = event.get("start_date")
    if not start_raw:
        return False
    try:
        start = date.fromisoformat(str(start_raw)[:10])
        end_raw = event.get("end_date") or start_raw
        end = date.fromisoformat(str(end_raw)[:10])
    except ValueError:
        return False
    today = date.today()
    return start <= today <= end + timedelta(days=5)


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
        or "/static/images/kapitolyo.jpg",
        "municipality": get_event_lgu_name(event),
        "summary": short,
        "description_html": event.get("full_description") or short,
        "date_month": month,
        "date_day": day,
        "time": event.get("venue_name") or event.get("venue") or "Venue TBA",
        "status": status,
        "is_featured_now": is_event_currently_featured(event),
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


def build_event_payload_from_form(
    form, files, *, forced_lgu_id: int | None = None, approval_status: str = "approved"
) -> dict[str, Any]:
    """Map Flask request form/files to events row.

    forced_lgu_id overrides whatever the form submitted — used when an
    lgu_admin creates an event, so they can't set another LGU's id via a
    tampered form field.

    approval_status controls whether the event goes live immediately
    ("approved", the default — LTCATO-created events) or needs review
    ("pending" — LGU-created events).
    """
    title = _strip(form.get("title")) or ""
    if not title:
        raise ValueError("Event title is required.")
    if not _strip(form.get("start_date")):
        raise ValueError("Event start date is required.")

    slug = _strip(form.get("slug")) or _slugify(title)
    # The dashboard only offers a draft/publish toggle now — "upcoming" is
    # just a non-draft placeholder that _compute_event_status() immediately
    # overrides from start_date/end_date on every read (see that function's
    # docstring). The stored value only still matters as the draft gate.
    event_status = "draft" if (_strip(form.get("event_status")) or "draft") == "draft" else "upcoming"
    visibility = _strip(form.get("visibility")) or "public"
    if visibility not in VISIBILITIES:
        visibility = "public"

    if forced_lgu_id is not None:
        lgu_id = forced_lgu_id
    else:
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
        "approval_status": approval_status if approval_status in ("pending", "approved", "rejected") else "approved",
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


def create_event_from_request(
    form,
    files,
    *,
    created_by: str | None,
    forced_lgu_id: int | None = None,
    approval_status: str = "approved",
) -> dict[str, Any]:
    payload = build_event_payload_from_form(
        form, files, forced_lgu_id=forced_lgu_id, approval_status=approval_status
    )
    if created_by:
        payload["created_by"] = created_by

    response = get_supabase().table("events").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Event was not saved.")
    event = response.data[0]
    try:
        _save_exhibitors_from_form(event["id"], form)
    except Exception:
        # The event itself is already committed at this point, so don't fail
        # the whole request (the user would otherwise resubmit and create a
        # duplicate event) — just flag it so the caller can warn instead.
        logger.exception("Failed to save exhibitors for event %s", event["id"])
        event["_exhibitor_save_failed"] = True
    return event


def update_event_from_request(
    event_id: int,
    form,
    files,
    *,
    forced_lgu_id: int | None = None,
    approval_status: str = "approved",
) -> dict[str, Any]:
    payload = build_event_payload_from_form(
        form, files, forced_lgu_id=forced_lgu_id, approval_status=approval_status
    )
    response = get_supabase().table("events").update(payload).eq("id", event_id).execute()
    if not response.data:
        raise RuntimeError("Event was not updated.")
    event = response.data[0]
    try:
        # Exhibitors are replaced wholesale rather than merged — the edit
        # form always resubmits the full current list. Insert the new rows
        # *before* removing the old ones: if the insert fails partway, the
        # pre-edit exhibitors are still there instead of already gone from
        # a delete-first approach.
        existing = (
            get_supabase()
            .table("event_exhibitors")
            .select("id")
            .eq("event_id", event_id)
            .execute()
        )
        old_ids = [row["id"] for row in (existing.data or [])]
        _save_exhibitors_from_form(event_id, form)
        if old_ids:
            get_supabase().table("event_exhibitors").delete().in_("id", old_ids).execute()
    except Exception:
        logger.exception("Failed to update exhibitors for event %s", event_id)
        event["_exhibitor_save_failed"] = True
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


def request_event_featured(
    event_id: int,
    *,
    requested_by: str,
    lgu_id: int | None = None,
    payment_reference: str | None = None,
) -> None:
    """LGU (or LTCATO staff, payment-free) requests an approved event be
    made Featured. Goes to featured_status='requested' pending LTCATO review."""
    response = (
        get_supabase()
        .table("events")
        .select("id, approval_status, lgu_id, featured_status")
        .eq("id", event_id)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise ValueError("Event not found.")
    event = rows[0]

    if lgu_id is not None and int(event.get("lgu_id") or -1) != int(lgu_id):
        raise PermissionError("You can only request Featured for your own LGU's events.")
    if event.get("approval_status") != "approved":
        raise ValueError("Only approved events can request Featured.")
    if event.get("featured_status") == "requested":
        raise ValueError("A featured request is already pending review.")

    get_supabase().table("events").update(
        {
            "featured_status": "requested",
            "featured_payment_reference": payment_reference,
            "featured_requested_at": datetime.now(timezone.utc).isoformat(),
            "featured_reviewed_at": None,
            "featured_reviewed_by": None,
        }
    ).eq("id", event_id).execute()


def review_event_featured(event_id: int, *, approve: bool, reviewed_by: str) -> None:
    get_supabase().table("events").update(
        {
            "featured_status": "approved" if approve else "rejected",
            "featured_reviewed_at": datetime.now(timezone.utc).isoformat(),
            "featured_reviewed_by": reviewed_by,
        }
    ).eq("id", event_id).execute()
