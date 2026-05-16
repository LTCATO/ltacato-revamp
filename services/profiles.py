"""
User profiles for dashboard account management.
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase

PROFILE_FIELDS = (
    "id, first_name, last_name, middle_name, email, role_id, lgu_id, "
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
