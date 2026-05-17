"""
Dashboard authentication and role-based navigation.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import flash, redirect, session, url_for

ROLE_LABELS: dict[str, str] = {
    "super_admin": "Super Admin (LTCATO Head)",
    "ltcato_staff": "LTCATO Staff",
    "lgu_admin": "LGU Officer",
    "establishment_owner": "Establishment Owner",
}



SESSION_KEYS = (
    "dashboard_user_id",
    "dashboard_email",
    "dashboard_name",
    "dashboard_role",
    "dashboard_organization",
    "dashboard_lgu_id",
)

NAV_BY_ROLE: dict[str, list[dict[str, Any]]] = {
    "super_admin": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"section": "Insights"},
        {"label": "Analytics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        {"label": "Decision support", "icon": "bx-brain", "endpoint": "dashboard.decision_support"},
        {"section": "Operations"},
        {"label": "Arrivals", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
        {"label": "Accounts", "icon": "bx-group", "endpoint": "dashboard.accounts"},
        {"label": "Promotions", "icon": "bx-calendar-event", "endpoint": "dashboard.promotions"},
        {"label": "Chatbot config", "icon": "bx-bot", "endpoint": "dashboard.chatbot"},
        {"label": "Feedback", "icon": "bx-message-square-dots", "endpoint": "dashboard.feedback"},
    ],
    "ltcato_staff": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"section": "Insights"},
        {"label": "Analytics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        {"label": "Decision support", "icon": "bx-brain", "endpoint": "dashboard.decision_support"},
        {"section": "Operations"},
        {"label": "Arrivals", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
        {"label": "LGU management", "icon": "bx-map", "endpoint": "dashboard.lgu_management"},
        {"label": "Promotions", "icon": "bx-calendar-event", "endpoint": "dashboard.promotions"},
        {"label": "Chatbot config", "icon": "bx-bot", "endpoint": "dashboard.chatbot"},
    ],
    "lgu_admin": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"label": "Analytics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        {"section": "LGU operations"},
        {"label": "Tourist spots", "icon": "bx-map", "endpoint": "dashboard.tourist_spots"},
        {"label": "Arrival data", "icon": "bx-upload", "endpoint": "dashboard.arrivals"},
        {"label": "Feedback", "icon": "bx-message-square-dots", "endpoint": "dashboard.feedback"},
    ],
    "establishment_owner": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"label": "Analytics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        {"section": "My establishment"},
        {"label": "Arrival data", "icon": "bx-edit", "endpoint": "dashboard.arrivals"},
        {"label": "Site updates", "icon": "bx-store", "endpoint": "dashboard.site_updates"},
    ],
}


def get_current_dashboard_user() -> dict[str, Any] | None:
    role = session.get("dashboard_role")
    if not role:
        return None
    return {
        "id": session.get("dashboard_user_id", ""),
        "email": session.get("dashboard_email", ""),
        "name": session.get("dashboard_name", "User"),
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "organization": session.get("dashboard_organization", ""),
        "lgu_id": session.get("dashboard_lgu_id"),
    }


def get_nav_items(role: str) -> list[dict[str, Any]]:
    return NAV_BY_ROLE.get(role, NAV_BY_ROLE["establishment_owner"])


def login_dashboard(email: str, password: str) -> tuple[bool, str | None]:
    email = email.strip().lower()
    from services.supabase_client import get_supabase
    from supabase import create_client
    import os

    url = os.getenv("SUPABASE_URL")
    # Must use anon key for sign-in to avoid mutating service_role client
    anon_key = os.getenv("SUPABASE_KEY")
    
    if not url or not anon_key:
        return False, "Server configuration error: missing Supabase credentials."

    temp_client = create_client(url, anon_key)
    
    try:
        response = temp_client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception:
        return False, "Invalid email or password for the staff portal."

    user = response.user
    if not user:
        return False, "Sign in failed. Please check your credentials."

    # Fetch profile using the global service_role client (bypasses RLS)
    profile_res = get_supabase().table("profiles").select("*, roles(role_key, role_name), lgus(name)").eq("id", user.id).execute()
    if not profile_res.data:
        return False, f"No dashboard profile found for this user (ID: {user.id})."

    profile = profile_res.data[0]
    role_info = profile.get("roles") or {}
    role_key = role_info.get("role_key")
    
    # Block tourists from logging into the dashboard
    if role_key == "tourist" or not role_key:
        get_supabase().auth.sign_out()
        return False, "Tourists cannot access the dashboard."

    first_name = profile.get("first_name") or ""
    last_name = profile.get("last_name") or ""
    name = f"{first_name} {last_name}".strip() or email.split("@")[0]
    
    org_name = "LTCATO"
    lgu_info = profile.get("lgus")
    if lgu_info and isinstance(lgu_info, dict):
        org_name = lgu_info.get("name") or org_name

    session["dashboard_user_id"] = user.id
    session["dashboard_email"] = email
    session["dashboard_name"] = name
    session["dashboard_role"] = role_key
    session["dashboard_organization"] = org_name
    session["dashboard_lgu_id"] = profile.get("lgu_id")
    
    return True, None


def logout_dashboard() -> None:
    for key in SESSION_KEYS:
        session.pop(key, None)





def request_path() -> str:
    from flask import request

    return request.full_path.rstrip("?") if request.query_string else request.path
