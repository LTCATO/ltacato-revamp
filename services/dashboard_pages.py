"""
Dashboard home overview content by role.
"""

from __future__ import annotations

from typing import Any

from services.dashboard_analytics import get_analytics_overview, get_establishment_analytics


def get_dashboard_overview(role: str, *, lgu_id: int | None = None) -> dict[str, Any]:
    analytics = get_analytics_overview(lgu_id=lgu_id) if role != "establishment_owner" else {}
    est = get_establishment_analytics() if role == "establishment_owner" else {}

    if role == "super_admin":
        stats = [
            {"icon": "bx-map", "label": "Approved spots", "value": analytics.get("spot_total", "—")},
            {"icon": "bx-time", "label": "Pending promotions", "value": analytics.get("pending_events", "—")},
            {"icon": "bx-bot", "label": "Chatbot pending", "value": analytics.get("pending_chatbot", "—")},
            {"icon": "bx-line-chart", "label": "Monthly visitors", "value": analytics.get("monthly_arrival_total", "—")},
        ]
        quick_actions = [
            {"label": "Analytics", "description": "System-wide tourism metrics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
            {"label": "Arrivals", "description": "Oversee monthly LGU reports (read-only)", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
            {"label": "Accounts", "description": "Staff & LGU accounts", "icon": "bx-group", "endpoint": "dashboard.accounts"},
            {"label": "Promotions", "description": "Approve staff events", "icon": "bx-calendar-event", "endpoint": "dashboard.promotions"},
        ]
        pending_tasks = [
            {"badge": "Events", "title": f"{analytics.get('pending_events', 0)} promotions awaiting approval", "due": "Review queue", "status": "warning"},
            {"badge": "Chatbot", "title": f"{analytics.get('pending_chatbot', 0)} FAQ entries pending", "due": "Knowledge base", "status": "info"},
            {"badge": "Spots", "title": f"{analytics.get('pending_ltcato_spots', 0)} spots for LTCATO review", "due": "After LGU", "status": "primary"},
        ]
    elif role == "ltcato_staff":
        stats = [
            {"icon": "bx-map", "label": "Approved spots", "value": analytics.get("spot_total", "—")},
            {"icon": "bx-buildings", "label": "Pending LTCATO", "value": analytics.get("pending_ltcato_spots", "—")},
            {"icon": "bx-calendar-event", "label": "Your events", "description": "", "value": "—"},
            {"icon": "bx-line-chart", "label": "Monthly arrivals", "value": analytics.get("monthly_arrival_total", "—")},
        ]
        quick_actions = [
            {"label": "LGU management", "description": "Confirm spots after LGU approval", "icon": "bx-map", "endpoint": "dashboard.lgu_management"},
            {"label": "Arrivals", "description": "Monthly totals from LGUs", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
            {"label": "Promotions", "description": "Post provincial events", "icon": "bx-calendar-event", "endpoint": "dashboard.promotions"},
            {"label": "Chatbot", "description": "Add FAQ for AI assistant", "icon": "bx-bot", "endpoint": "dashboard.chatbot"},
        ]
        pending_tasks = [
            {"badge": "Spots", "title": f"{analytics.get('pending_ltcato_spots', 0)} establishments to confirm", "due": "LGU management", "status": "warning"},
            {"badge": "Arrivals", "title": "Review monthly LGU submissions", "due": "This month", "status": "primary"},
        ]
    elif role == "lgu_admin":
        stats = [
            {"icon": "bx-store", "label": "Managed spots", "value": analytics.get("spot_total", "—")},
            {"icon": "bx-message", "label": "Feedback received", "value": analytics.get("feedback_count", "—")},
            {"icon": "bx-star", "label": "Avg rating", "value": analytics.get("avg_feedback_rating", "—")},
            {"icon": "bx-upload", "label": "Monthly to LTCATO", "value": "Submit", "description": ""},
        ]
        quick_actions = [
            {"label": "Tourist spots", "description": "Establishments under your LGU", "icon": "bx-map", "endpoint": "dashboard.tourist_spots"},
            {"label": "Arrival data", "description": "Daily/weekly in, monthly out", "icon": "bx-upload", "endpoint": "dashboard.arrivals"},
            {"label": "Feedback", "description": "Tourist comments on spots", "icon": "bx-message-square-dots", "endpoint": "dashboard.feedback"},
            {"label": "Analytics", "description": "LGU & establishment metrics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        ]
        pending_tasks = [
            {"badge": "Arrivals", "title": "Compile monthly totals per establishment", "due": "End of month", "status": "warning"},
            {"badge": "Accounts", "title": "Create owner accounts for new establishments", "due": "Tourist spots", "status": "info"},
        ]
    else:
        stats = [
            {"icon": "bx-user", "label": "Visitors (weekly)", "value": est.get("visitors_this_month", "—")},
            {"icon": "bx-file", "label": "Reports filed", "value": est.get("reports_submitted", "—")},
            {"icon": "bx-star", "label": "Avg rating", "value": est.get("avg_rating", "—")},
            {"icon": "bx-time", "label": "Due reports", "value": est.get("pending_reports", "—")},
        ]
        quick_actions = [
            {"label": "Arrival data", "description": "Submit daily or weekly counts", "icon": "bx-edit", "endpoint": "dashboard.arrivals"},
            {"label": "Site updates", "description": "Update your listing", "icon": "bx-store", "endpoint": "dashboard.site_updates"},
            {"label": "Analytics", "description": "Your establishment metrics", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        ]
        pending_tasks = [
            {"badge": "Report", "title": "Submit weekly arrival to your LGU", "due": "This week", "status": "warning"},
            {"badge": "Listing", "title": "Keep photos and hours up to date", "due": "Site updates", "status": "info"},
        ]

    arrival_pipeline = [
        {"step": "1", "icon": "bx-store", "title": "Establishment", "text": "Owner submits daily or weekly visitor counts."},
        {"step": "2", "icon": "bx-buildings", "title": "LGU", "text": "LGU consolidates reports and forwards monthly totals."},
        {"step": "3", "icon": "bx-briefcase", "title": "LTCATO Staff", "text": "Staff receives and validates monthly LGU submissions."},
        {"step": "4", "icon": "bx-crown", "title": "Super Admin", "text": "Head office oversees provincial arrival analytics."},
    ]

    recent_activity = [
        {"icon": "bx-check-circle", "message": "Dashboard connected to Supabase tourism data.", "time": "Live"},
        {"icon": "bx-data", "message": "Arrivals use arrival_reports (daily, weekly, monthly).", "time": "Schema v2"},
    ]

    public_modules = [
        {"label": "Tourist spots", "description": "Browse approved destinations", "icon": "bx-map", "endpoint": "spots.spots_list"},
        {"label": "Events", "description": "Approved promotions & festivals", "icon": "bx-calendar", "endpoint": "events.events_list"},
        {"label": "LGU directory", "description": "Cities and municipalities", "icon": "bx-buildings", "endpoint": "lgu.lgu_list"},
    ]

    return {
        "stats": stats,
        "quick_actions": quick_actions,
        "pending_tasks": pending_tasks,
        "arrival_pipeline": arrival_pipeline,
        "recent_activity": recent_activity,
        "public_modules": public_modules,
        "analytics": analytics,
    }


def get_workflow_cards(role: str) -> list[dict[str, Any]]:
    cards: dict[str, list[dict[str, Any]]] = {
        "super_admin": [
            {"title": "Analytics", "text": "Provincial KPIs across LGUs, spots, and arrivals.", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
            {"title": "Decision support", "text": "Scraped web & social reviews with sentiment.", "icon": "bx-brain", "endpoint": "dashboard.decision_support"},
            {"title": "Accounts", "text": "Create LTCATO staff and LGU portal users.", "icon": "bx-group", "endpoint": "dashboard.accounts"},
            {"title": "Feedback", "text": "System-wide tourist feedback oversight.", "icon": "bx-message-square-dots", "endpoint": "dashboard.feedback"},
        ],
        "ltcato_staff": [
            {"title": "LGU management", "text": "Approve spots after LGU tourism sign-off.", "icon": "bx-map", "endpoint": "dashboard.lgu_management"},
            {"title": "Arrivals", "text": "Monthly reports submitted by LGUs.", "icon": "bx-line-chart", "endpoint": "dashboard.arrivals"},
            {"title": "Promotions", "text": "Post events pending super admin approval.", "icon": "bx-calendar-event", "endpoint": "dashboard.promotions"},
            {"title": "Chatbot", "text": "Maintain FAQ entries for the AI assistant.", "icon": "bx-bot", "endpoint": "dashboard.chatbot"},
        ],
        "lgu_admin": [
            {"title": "Analytics", "text": "Dashboard for your LGU and establishments.", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
            {"title": "Decision support", "text": "Spot insights and feedback scoped to your municipality.", "icon": "bx-brain", "endpoint": "dashboard.decision_support"},
            {"title": "Tourist spots", "text": "Create owner accounts; owners register their spots.", "icon": "bx-map", "endpoint": "dashboard.tourist_spots"},
            {"title": "Feedback", "text": "Comments from tourists on your spots.", "icon": "bx-message-square-dots", "endpoint": "dashboard.feedback"},
        ],
        "establishment_owner": [
            {"title": "Arrival data", "text": "Pass daily or weekly counts to your LGU.", "icon": "bx-edit", "endpoint": "dashboard.arrivals"},
            {"title": "Decision support", "text": "Feedback insights and ratings for your establishment.", "icon": "bx-brain", "endpoint": "dashboard.decision_support"},
            {"title": "Site updates", "text": "Photos, hours, and experience details.", "icon": "bx-store", "endpoint": "dashboard.site_updates"},
            {"title": "Analytics", "text": "Visitors and ratings for your property.", "icon": "bx-bar-chart-alt-2", "endpoint": "dashboard.analytics"},
        ],
    }
    return cards.get(role, cards["establishment_owner"])
