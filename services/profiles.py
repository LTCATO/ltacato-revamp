"""
User profiles for dashboard account management.
"""

from __future__ import annotations

from typing import Any

# pyrefly: ignore [missing-import]
from postgrest.exceptions import APIError

from services.supabase_client import get_supabase, reset_supabase

# PostgREST's code for ".single() matched zero rows" — the only case that
# genuinely means "no profile exists". Any other error (timeout, connection
# reset, etc.) is a real failure and must not be treated the same way.
_NO_ROWS_CODE = "PGRST116"

PROFILE_FIELDS = (
    "id, first_name, last_name, middle_name, email, role_id, lgu_id, position, "
    "is_active, created_at, "
    "roles(id, role_key, role_name), lgus(id, name)"
)


def list_profiles(*, role_key: str | None = None, lgu_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = get_supabase().table("profiles").select(PROFILE_FIELDS)
    if lgu_id:
        query = query.eq("lgu_id", lgu_id)
    response = query.order("created_at", desc=True).limit(limit).execute()
    rows = response.data or []
    if role_key:
        filtered = []
        for row in rows:
            role = row.get("roles") or {}
            if isinstance(role, dict) and role.get("role_key") == role_key:
                filtered.append(row)
        return filtered
    return rows


def profile_display_name(row: dict[str, Any]) -> str:
    parts = [row.get("first_name"), row.get("last_name")]
    name = " ".join(p for p in parts if p).strip()
    return name or row.get("email") or "User"


def profile_role_label(row: dict[str, Any]) -> str:
    role = row.get("roles") or {}
    if isinstance(role, dict):
        return role.get("role_name") or role.get("role_key") or "—"
    return "—"


def get_dashboard_profile(user_id: str) -> dict[str, Any] | None:
    """Fetch a dashboard user's full profile (all roles)."""
    try:
        response = (
            get_supabase()
            .table("profiles")
            .select(PROFILE_FIELDS)
            .eq("id", user_id)
            .single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def update_dashboard_profile(
    user_id: str,
    *,
    first_name: str,
    last_name: str,
    middle_name: str = "",
    position: str = "",
) -> tuple[bool, str | None]:
    """Update name/position for a dashboard user (all roles)."""
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    middle_name = (middle_name or "").strip()
    position = (position or "").strip()

    if len(first_name) < 2:
        return False, "Please enter your first name (at least 2 characters)."
    if len(last_name) < 2:
        return False, "Please enter your last name (at least 2 characters)."

    payload: dict[str, Any] = {
        "first_name": first_name,
        "last_name": last_name,
        "middle_name": middle_name or None,
        "position": position or None,
    }

    try:
        get_supabase().table("profiles").update(payload).eq("id", user_id).execute()
        return True, None
    except Exception:
        return False, "Unable to update profile. Please try again."


TOURIST_PROFILE_FIELDS = (
    "id, first_name, last_name, middle_name, email, profile_image, created_at, "
    "roles(id, role_key, role_name)"
)


def get_tourist_profile(user_id: str) -> dict[str, Any] | None:
    """Returns None only when the tourist genuinely has no profile row.
    Any other failure (e.g. a transient connection error) raises, so callers
    don't mistake "the query failed" for "this account has no profile" and
    bounce a real user home.

    The shared Supabase client's connection has been observed to go bad for
    this specific query on a long-running process while a brand-new client
    succeeds immediately — so a failure that isn't "genuinely not found" gets
    one retry against a freshly-built client before giving up."""
    for attempt in (1, 2):
        try:
            response = (
                get_supabase()
                .table("profiles")
                .select(TOURIST_PROFILE_FIELDS)
                .eq("id", user_id)
                .single()
                .execute()
            )
            return response.data
        except APIError as exc:
            if exc.code == _NO_ROWS_CODE:
                return None
            if attempt == 1:
                reset_supabase()
                continue
            raise
        except Exception:
            if attempt == 1:
                reset_supabase()
                continue
            raise
    return None  # unreachable, keeps type-checkers happy


def update_tourist_profile(
    user_id: str,
    *,
    first_name: str,
    last_name: str,
    middle_name: str = "",
    profile_image: str | None = None,
) -> tuple[bool, str | None]:
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    middle_name = (middle_name or "").strip()

    if len(first_name) < 2:
        return False, "Please enter your first name."
    if len(last_name) < 2:
        return False, "Please enter your last name."

    payload: dict[str, Any] = {
        "first_name": first_name,
        "last_name": last_name,
        "middle_name": middle_name or None,
    }
    if profile_image is not None:
        payload["profile_image"] = profile_image.strip() or None

    try:
        get_supabase().table("profiles").update(payload).eq("id", user_id).execute()
        return True, None
    except Exception:
        return False, "Unable to update your profile right now. Please try again."
