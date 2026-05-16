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
    "lgu": "LGU Officer",
    "establishment_owner": "Establishment Owner",
}

DEMO_USERS: dict[str, dict[str, Any]] = {
    "superadmin@ltcato.gov.ph": {
        "password": "ltcato2026",
        "role": "super_admin",
        "name": "LTCATO Super Admin",
        "organization": "Provincial Government of Laguna",
        "lgu_id": None,
    },
    "staff@ltcato.gov.ph": {
        "password": "ltcato2026",
        "role": "ltcato_staff",
        "name": "Maria Santos",
        "organization": "LTCATO — Tourism Division",
        "lgu_id": None,
    },
    "lgu@calamba.gov.ph": {
        "password": "ltcato2026",
        "role": "lgu",
        "name": "Calamba LGU Tourism",
        "organization": "City of Calamba",
        "lgu_id": 1,
    },
    "owner@hotspring.laguna.ph": {
        "password": "ltcato2026",
        "role": "establishment_owner",
        "name": "Resort Manager",
        "organization": "Sample Thermal Resort",
        "lgu_id": 1,
        "owner_id": "demo-owner-uuid",
    },
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
    "lgu": [
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
    user = DEMO_USERS.get(email)
    if not user or user["password"] != password:
        return False, "Invalid email or password for the staff portal."

    session["dashboard_user_id"] = email
    session["dashboard_email"] = email
    session["dashboard_name"] = user["name"]
    session["dashboard_role"] = user["role"]
    session["dashboard_organization"] = user["organization"]
    session["dashboard_lgu_id"] = user.get("lgu_id")
    return True, None


def logout_dashboard() -> None:
    for key in SESSION_KEYS:
        session.pop(key, None)


def get_demo_accounts() -> list[dict[str, str]]:
    return [
        {
            "email": email,
            "role": ROLE_LABELS[data["role"]],
            "role_key": data["role"],
            "name": data["name"],
        }
        for email, data in DEMO_USERS.items()
    ]


def request_path() -> str:
    from flask import request

    return request.full_path.rstrip("?") if request.query_string else request.path
