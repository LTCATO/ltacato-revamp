"""
User profiles for dashboard account management.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

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


TOURIST_PROFILE_FIELDS = (
    "id, first_name, last_name, middle_name, email, profile_image, created_at, "
    "roles(id, role_key, role_name)"
)


def get_tourist_profile(user_id: str) -> dict[str, Any] | None:
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
    except Exception:
        return None


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
