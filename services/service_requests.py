"""
Citizen-facing request intake for LTCATO's Citizen's Charter services.

Digitizes the "submit a letter of request" step common to all 8 charter
services (see services/citizen_charter.py) — Tourism Division and History,
Arts & Culture Division alike — as a single generic form and staff queue,
instead of a dedicated feature per service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.citizen_charter import CHARTER_SECTIONS
from services.supabase_client import get_supabase

STATUSES = ("submitted", "under_review", "responded")

REQUEST_FIELDS = (
    "id, service_number, service_title, division, tourist_id, "
    "requester_name, requester_email, requester_phone, message, status, "
    "staff_response, handled_by, created_at, updated_at"
)


def get_service_catalog() -> list[dict[str, Any]]:
    """Flatten the charter's services into {number, title, division} for the
    request form's dropdown and the staff queue's filter — the catalog
    itself always lives in citizen_charter.py, never duplicated here."""
    catalog: list[dict[str, Any]] = []
    for section in CHARTER_SECTIONS:
        for service in section["services"]:
            catalog.append(
                {
                    "number": service["number"],
                    "title": service["title"],
                    "division": service["division"],
                }
            )
    return catalog


def _find_service(service_number: int) -> dict[str, Any] | None:
    for service in get_service_catalog():
        if service["number"] == service_number:
            return service
    return None


def create_service_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate against the live charter catalog and insert a new request.
    Raises ValueError on bad input (caller turns that into a form error)."""
    try:
        service_number = int(payload.get("service_number"))
    except (TypeError, ValueError):
        raise ValueError("Select which service you're requesting.")
    service = _find_service(service_number)
    if not service:
        raise ValueError("That service isn't in the current charter.")

    requester_name = (payload.get("requester_name") or "").strip()
    requester_email = (payload.get("requester_email") or "").strip().lower()
    message = (payload.get("message") or "").strip()
    if not requester_name or not requester_email or not message:
        raise ValueError("Name, email, and a message are required.")

    row = {
        "service_number": service["number"],
        "service_title": service["title"],
        "division": service["division"],
        "tourist_id": payload.get("tourist_id"),
        "requester_name": requester_name,
        "requester_email": requester_email,
        "requester_phone": (payload.get("requester_phone") or "").strip() or None,
        "message": message,
        "status": "submitted",
    }
    response = get_supabase().table("service_requests").insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Failed to save the request.")
    return data[0]


def get_user_service_requests(tourist_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = (
        get_supabase()
        .table("service_requests")
        .select(REQUEST_FIELDS)
        .eq("tourist_id", tourist_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    return rows


def list_service_requests(
    *,
    status: str | None = None,
    division: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = get_supabase().table("service_requests").select(REQUEST_FIELDS)
    if status in STATUSES:
        query = query.eq("status", status)
    if division:
        query = query.eq("division", division)
    return query.order("created_at", desc=True).limit(limit).execute().data or []


def update_service_request_status(
    request_id: int,
    *,
    status: str,
    staff_response: str | None,
    handled_by: str | None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError("Invalid status.")
    row = {
        "status": status,
        "staff_response": (staff_response or "").strip() or None,
        "handled_by": handled_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    response = (
        get_supabase()
        .table("service_requests")
        .update(row)
        .eq("id", request_id)
        .execute()
    )
    data = response.data or []
    if not data:
        raise RuntimeError("Failed to update the request.")
    return data[0]
