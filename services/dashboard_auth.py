"""
Dashboard authentication and role-based navigation for LTCATO staff portal.
Replace demo users with Supabase Auth + profiles when the database schema is ready.
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

# Demo accounts for development — password: ltcato2026
DEMO_USERS: dict[str, dict[str, str]] = {
    "superadmin@ltcato.gov.ph": {
        "password": "ltcato2026",
        "role": "super_admin",
        "name": "LTCATO Super Admin",
        "organization": "Provincial Government of Laguna",
    },
    "staff@ltcato.gov.ph": {
        "password": "ltcato2026",
        "role": "ltcato_staff",
        "name": "Maria Santos",
        "organization": "LTCATO — Tourism Division",
    },
    "lgu@calamba.gov.ph": {
        "password": "ltcato2026",
        "role": "lgu",
        "name": "Calamba LGU Tourism",
        "organization": "City of Calamba",
    },
    "owner@hotspring.laguna.ph": {
        "password": "ltcato2026",
        "role": "establishment_owner",
        "name": "Resort Manager",
        "organization": "Sample Thermal Resort",
    },
}

SESSION_KEYS = (
    "dashboard_user_id",
    "dashboard_email",
    "dashboard_name",
    "dashboard_role",
    "dashboard_organization",
)

NAV_BY_ROLE: dict[str, list[dict[str, Any]]] = {
    "super_admin": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"section": "Tourism data"},
        {"label": "Tourist arrivals", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
        {"label": "Reports", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.reports"},
        {"section": "Management"},
        {"label": "Events & promotion", "icon": "bx-calendar-event", "endpoint": "dashboard.events"},
        {"label": "Tourist spots", "icon": "bx-map", "endpoint": "dashboard.spots"},
        {"label": "Accounts", "icon": "bx-group", "endpoint": "dashboard.accounts"},
        {"section": "System"},
        {"label": "Settings", "icon": "bx-cog", "endpoint": "dashboard.settings"},
    ],
    "ltcato_staff": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"section": "Programs"},
        {"label": "Events & promotion", "icon": "bx-calendar-event", "endpoint": "dashboard.events"},
        {"label": "Tourist spots", "icon": "bx-map", "endpoint": "dashboard.spots"},
        {"label": "Tourist arrivals", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
    ],
    "lgu": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"section": "LGU operations"},
        {"label": "Staff accounts", "icon": "bx-user", "endpoint": "dashboard.staff_accounts"},
        {"label": "Establishments", "icon": "bx-buildings", "endpoint": "dashboard.establishments"},
        {"label": "Arrival submissions", "icon": "bx-upload", "endpoint": "dashboard.arrivals"},
        {"label": "Monthly report to LTCATO", "icon": "bx-send", "endpoint": "dashboard.monthly_report"},
    ],
    "establishment_owner": [
        {"section": "Overview"},
        {"label": "Dashboard", "icon": "bx-grid-alt", "endpoint": "dashboard.index"},
        {"section": "My establishment"},
        {"label": "Profile & details", "icon": "bx-store", "endpoint": "dashboard.my_establishment"},
        {"label": "Submit arrivals", "icon": "bx-edit", "endpoint": "dashboard.submit_arrivals"},
        {"label": "Submission history", "icon": "bx-history", "endpoint": "dashboard.arrival_history"},
    ],
}

WORKFLOW_SUMMARY: dict[str, list[dict[str, str]]] = {
    "super_admin": [
        {
            "title": "Receive monthly arrivals",
            "text": "LGUs consolidate daily/weekly staff submissions and send monthly reports to LTCATO.",
            "icon": "bx-download",
        },
        {
            "title": "Manage provincial accounts",
            "text": "Create and oversee LGU, establishment, staff, and tourist accounts.",
            "icon": "bx-group",
        },
        {
            "title": "Promote Laguna",
            "text": "Publish festivals and events such as Anilag on the public site.",
            "icon": "bx-megaphone",
        },
    ],
    "ltcato_staff": [
        {
            "title": "Support promotions",
            "text": "Coordinate event listings and tourism programs with divisions.",
            "icon": "bx-calendar-star",
        },
        {
            "title": "Review spot data",
            "text": "Help maintain accurate tourist spot information on the public portal.",
            "icon": "bx-map-alt",
        },
    ],
    "lgu": [
        {
            "title": "Manage establishment staff",
            "text": "Onboard establishments that submit daily or weekly arrival counts.",
            "icon": "bx-user-plus",
        },
        {
            "title": "Consolidate arrivals",
            "text": "Review staff submissions and forward the monthly total to LTCATO.",
            "icon": "bx-spreadsheet",
        },
    ],
    "establishment_owner": [
        {
            "title": "Update your listing",
            "text": "Keep establishment details, photos, and contact information current.",
            "icon": "bx-edit-alt",
        },
        {
            "title": "Report visitor counts",
            "text": "Pass daily or weekly tourist arrival data to your LGU.",
            "icon": "bx-trending-up",
        },
    ],
}


def get_current_dashboard_user() -> dict[str, str] | None:
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
    }


def get_nav_items(role: str) -> list[dict[str, Any]]:
    return NAV_BY_ROLE.get(role, NAV_BY_ROLE["establishment_owner"])


def get_workflow_cards(role: str) -> list[dict[str, str]]:
    return WORKFLOW_SUMMARY.get(role, [])


QUICK_ACTIONS: dict[str, list[dict[str, str]]] = {
    "super_admin": [
        {
            "label": "Review arrivals",
            "endpoint": "dashboard.arrivals",
            "icon": "bx-line-chart",
            "description": "Monthly LGU submissions",
        },
        {
            "label": "Manage accounts",
            "endpoint": "dashboard.accounts",
            "icon": "bx-group",
            "description": "LGUs, establishments, tourists",
        },
        {
            "label": "Post an event",
            "endpoint": "dashboard.events",
            "icon": "bx-calendar-event",
            "description": "Festivals & promotions",
        },
        {
            "label": "Tourist spots",
            "endpoint": "dashboard.spots",
            "icon": "bx-map",
            "description": "Provincial directory",
        },
    ],
    "ltcato_staff": [
        {
            "label": "Events & promotion",
            "endpoint": "dashboard.events",
            "icon": "bx-calendar-event",
            "description": "Anilag and provincial fairs",
        },
        {
            "label": "Spot listings",
            "endpoint": "dashboard.spots",
            "icon": "bx-map",
            "description": "Verify public listings",
        },
        {
            "label": "Arrival reports",
            "endpoint": "dashboard.arrivals",
            "icon": "bx-bar-chart",
            "description": "Tourism statistics",
        },
    ],
    "lgu": [
        {
            "label": "Staff accounts",
            "endpoint": "dashboard.staff_accounts",
            "icon": "bx-user",
            "description": "Establishment logins",
        },
        {
            "label": "Review submissions",
            "endpoint": "dashboard.arrivals",
            "icon": "bx-upload",
            "description": "Daily / weekly counts",
        },
        {
            "label": "Monthly to LTCATO",
            "endpoint": "dashboard.monthly_report",
            "icon": "bx-send",
            "description": "Provincial handoff",
        },
        {
            "label": "Establishments",
            "endpoint": "dashboard.establishments",
            "icon": "bx-buildings",
            "description": "Under your LGU",
        },
    ],
    "establishment_owner": [
        {
            "label": "Submit arrivals",
            "endpoint": "dashboard.submit_arrivals",
            "icon": "bx-edit",
            "description": "Daily or weekly counts",
        },
        {
            "label": "My establishment",
            "endpoint": "dashboard.my_establishment",
            "icon": "bx-store",
            "description": "Profile & photos",
        },
        {
            "label": "Submission history",
            "endpoint": "dashboard.arrival_history",
            "icon": "bx-history",
            "description": "Past reports",
        },
    ],
}

PENDING_TASKS: dict[str, list[dict[str, str]]] = {
    "super_admin": [
        {
            "title": "Calamba LGU — March monthly report",
            "status": "pending",
            "due": "Due in 3 days",
            "badge": "LGU",
        },
        {
            "title": "San Pablo City — weekly consolidation",
            "status": "review",
            "due": "Awaiting review",
            "badge": "LGU",
        },
        {
            "title": "Anilag 2026 event draft",
            "status": "draft",
            "due": "Promotion queue",
            "badge": "Event",
        },
    ],
    "ltcato_staff": [
        {
            "title": "12 spot listings pending verification",
            "status": "review",
            "due": "This week",
            "badge": "Spots",
        },
        {
            "title": "Heritage tour webinar materials",
            "status": "pending",
            "due": "Friday",
            "badge": "Program",
        },
    ],
    "lgu": [
        {
            "title": "Thermal Resort — weekly arrival (W12)",
            "status": "pending",
            "due": "Overdue 1 day",
            "badge": "Staff",
        },
        {
            "title": "Heritage Museum — daily count (May 14)",
            "status": "submitted",
            "due": "Received",
            "badge": "Staff",
        },
        {
            "title": "March monthly report to LTCATO",
            "status": "draft",
            "due": "Due May 31",
            "badge": "Provincial",
        },
    ],
    "establishment_owner": [
        {
            "title": "Weekly arrival — current week",
            "status": "pending",
            "due": "Due Sunday",
            "badge": "Report",
        },
        {
            "title": "Update summer operating hours",
            "status": "draft",
            "due": "Profile",
            "badge": "Listing",
        },
    ],
}

RECENT_ACTIVITY: dict[str, list[dict[str, str]]] = {
    "super_admin": [
        {"icon": "bx-download", "message": "Los Baños LGU submitted March monthly arrivals.", "time": "2 hours ago"},
        {"icon": "bx-user-plus", "message": "New establishment account: Paete Woodcarving Center.", "time": "Yesterday"},
        {"icon": "bx-calendar", "message": "Anilag festival page scheduled for public site.", "time": "2 days ago"},
    ],
    "ltcato_staff": [
        {"icon": "bx-check", "message": "Approved tourist spot: Hidden Garden Springs.", "time": "4 hours ago"},
        {"icon": "bx-edit", "message": "Updated event copy for Pahiyas showcase.", "time": "Yesterday"},
    ],
    "lgu": [
        {"icon": "bx-upload", "message": "Sample Thermal Resort submitted weekly arrivals.", "time": "1 hour ago"},
        {"icon": "bx-error", "message": "Reminder sent to 2 establishments with missing daily counts.", "time": "Today"},
    ],
    "establishment_owner": [
        {"icon": "bx-check", "message": "Weekly arrival for W11 accepted by Calamba LGU.", "time": "3 days ago"},
        {"icon": "bx-image", "message": "Gallery photos updated on public listing.", "time": "Last week"},
    ],
}

ARRIVAL_PIPELINE: list[dict[str, str]] = [
    {
        "step": "1",
        "title": "Establishment",
        "text": "Owners submit daily or weekly visitor counts to their LGU.",
        "icon": "bx-store",
    },
    {
        "step": "2",
        "title": "LGU",
        "text": "LGUs review staff submissions and consolidate municipality data.",
        "icon": "bx-buildings",
    },
    {
        "step": "3",
        "title": "Monthly report",
        "text": "LGUs forward monthly totals to LTCATO for provincial planning.",
        "icon": "bx-send",
    },
    {
        "step": "4",
        "title": "LTCATO",
        "text": "Super admin and staff analyze arrivals for tourism programs.",
        "icon": "bx-line-chart",
    },
]

PUBLIC_MODULES: list[dict[str, str]] = [
    {
        "label": "Tourist spots",
        "endpoint": "spots.spots_list",
        "icon": "bx-map",
        "description": "Verified destinations",
    },
    {
        "label": "Events",
        "endpoint": "events.events_list",
        "icon": "bx-calendar-event",
        "description": "Festivals & fairs",
    },
    {
        "label": "About LTCATO",
        "endpoint": "public.about",
        "icon": "bx-info-circle",
        "description": "Charter & offices",
    },
]


def _fetch_spot_total() -> int | None:
    try:
        from services.spots import list_spots

        _, total = list_spots(page=1)
        return total
    except Exception:
        return None


def get_dashboard_stats(role: str) -> list[dict[str, str]]:
    spot_total = _fetch_spot_total()
    spots_display = f"{spot_total}+" if spot_total and spot_total >= 100 else (str(spot_total) if spot_total is not None else "150+")

    common = [
        {"icon": "bx-map", "value": spots_display, "label": "Verified tourist spots"},
        {"icon": "bx-buildings", "value": "30", "label": "Municipalities & cities"},
    ]

    role_stats: dict[str, list[dict[str, str]]] = {
        "super_admin": [
            *common,
            {"icon": "bx-line-chart", "value": "24", "label": "LGU reports this quarter"},
            {"icon": "bx-calendar-event", "value": "8", "label": "Active promotions"},
        ],
        "ltcato_staff": [
            *common,
            {"icon": "bx-calendar-event", "value": "5", "label": "Events in pipeline"},
            {"icon": "bx-time", "value": "12", "label": "Spots pending review"},
        ],
        "lgu": [
            {"icon": "bx-store", "value": "18", "label": "Establishments under LGU"},
            {"icon": "bx-user", "value": "18", "label": "Staff accounts"},
            {"icon": "bx-check-circle", "value": "14", "label": "Weekly reports received"},
            {"icon": "bx-error", "value": "4", "label": "Missing submissions"},
        ],
        "establishment_owner": [
            {"icon": "bx-trending-up", "value": "1,240", "label": "Visitors this month"},
            {"icon": "bx-star", "value": "4.6", "label": "Average review rating"},
            {"icon": "bx-check", "value": "11", "label": "Reports submitted YTD"},
            {"icon": "bx-time", "value": "1", "label": "Pending this week"},
        ],
    }
    return role_stats.get(role, common)


def get_dashboard_overview(role: str) -> dict[str, Any]:
    return {
        "stats": get_dashboard_stats(role),
        "quick_actions": QUICK_ACTIONS.get(role, []),
        "pending_tasks": PENDING_TASKS.get(role, []),
        "recent_activity": RECENT_ACTIVITY.get(role, []),
        "arrival_pipeline": ARRIVAL_PIPELINE,
        "public_modules": PUBLIC_MODULES,
    }


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


def dashboard_login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_dashboard_user():
            flash("Please sign in to access the dashboard.", "warning")
            return redirect(url_for("dashboard.login", next=request_path()))
        return view(*args, **kwargs)

    return wrapped


def request_path() -> str:
    from flask import request

    return request.full_path.rstrip("?") if request.query_string else request.path
