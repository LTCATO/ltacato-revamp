"""
Single source of truth for what a chat user is allowed to see.

Resolves role/lgu_id/owner_id/spot_ids strictly from the server-side
session — never from the request body. This is the enforcement point that
keeps LARA from trusting a client-submitted role/lgu_id to escalate access;
see services/chatbot_context.py for where this scope is actually applied
to database queries.
"""

from __future__ import annotations

from typing import Any

from services.dashboard_auth import get_current_dashboard_user
from services.spots import list_owner_spot_ids
from services.tourist_auth import get_current_tourist

_DEFAULT_SCOPE: dict[str, Any] = {
    "role": "tourist",
    "user_id": None,
    "lgu_id": None,
    "owner_id": None,
    "spot_ids": None,
    "display_name": None,
}


def resolve_chat_scope() -> dict[str, Any]:
    db_user = get_current_dashboard_user()
    if db_user:
        role = db_user.get("role") or "tourist"
        scope: dict[str, Any] = {
            "role": role,
            "user_id": db_user.get("id"),
            "lgu_id": None,
            "owner_id": None,
            "spot_ids": None,
            "display_name": db_user.get("name"),
        }
        if role == "lgu_admin":
            scope["lgu_id"] = db_user.get("lgu_id")
        elif role == "establishment_owner":
            owner_id = db_user.get("id")
            scope["owner_id"] = owner_id
            scope["spot_ids"] = list_owner_spot_ids(str(owner_id)) if owner_id else []
        # ltcato_staff / super_admin stay province-wide (lgu_id=None, owner_id=None)
        return scope

    tourist = get_current_tourist()
    if tourist:
        return {
            **_DEFAULT_SCOPE,
            "user_id": tourist.get("id"),
            "display_name": tourist.get("name"),
        }

    return dict(_DEFAULT_SCOPE)
