# pyrefly: ignore [missing-import]
from flask import flash, redirect, request, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required, render_dashboard, role_required
from services.arrival_reports import list_arrival_reports
from services.chatbot_knowledge import list_knowledge
from services.dashboard_analytics import get_analytics_overview, get_establishment_analytics
from services.dashboard_auth import get_current_dashboard_user
from services.dashboard_pages import get_dashboard_overview, get_workflow_cards
from services.events import list_events
from services.external_reviews import list_external_reviews
from services.feedbacks import list_feedbacks
from services.lgus import list_lgus_simple
from services.profiles import list_profiles
from services.spots import list_spots_for_dashboard


def _user_lgu_id(user: dict) -> int | None:
    lid = user.get("lgu_id")
    return int(lid) if lid is not None else None


@dashboard_bp.route("/")
@dashboard_login_required
def index():
    user = get_current_dashboard_user()
    role = user["role"]
    overview = get_dashboard_overview(role, lgu_id=_user_lgu_id(user))
    workflow_cards = get_workflow_cards(role)
    for i, card in enumerate(workflow_cards):
        if i < len(overview["quick_actions"]):
            card["endpoint"] = overview["quick_actions"][i]["endpoint"]
    return render_dashboard(
        "views/dashboard/index.html",
        user,
        overview=overview,
        workflow_cards=workflow_cards,
    )


@dashboard_bp.route("/analytics")
@dashboard_login_required
def analytics():
    user = get_current_dashboard_user()
    lgu_id = _user_lgu_id(user)
    if user["role"] == "establishment_owner":
        data = get_establishment_analytics()
    else:
        data = get_analytics_overview(lgu_id=lgu_id if user["role"] == "lgu_admin" else None)
    return render_dashboard(
        "views/dashboard/pages/analytics.html",
        user,
        analytics=data,
        page_title="Analytics",
        page_description="Tourism metrics and trends for your scope.",
        page_icon="bx-bar-chart-alt-2",
    )


@dashboard_bp.route("/decision-support")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def decision_support():
    user = get_current_dashboard_user()
    reviews = list_external_reviews(limit=80)
    return render_dashboard(
        "views/dashboard/pages/decision_support.html",
        user,
        reviews=reviews,
        page_title="Decision support",
        page_description="Web and social media reviews scraped for sentiment analysis.",
        page_icon="bx-brain",
    )


@dashboard_bp.route("/arrivals")
@dashboard_login_required
def arrivals():
    user = get_current_dashboard_user()
    role = user["role"]
    lgu_id = _user_lgu_id(user)

    if role == "establishment_owner":
        reports = list_arrival_reports(spot_id=None, report_type=None, limit=50)
        report_types = ("daily", "weekly")
        page_desc = "Submit daily or weekly visitor counts to your LGU."
    elif role == "lgu_admin":
        reports = list_arrival_reports(lgu_id=lgu_id, limit=100)
        report_types = ("daily", "weekly", "monthly")
        page_desc = "Receive establishment reports and submit monthly totals to LTCATO staff."
    elif role == "ltcato_staff":
        reports = list_arrival_reports(report_type="monthly", limit=100)
        report_types = ("monthly",)
        page_desc = "Monthly arrival totals submitted by LGUs."
    else:
        reports = list_arrival_reports(report_type="monthly", limit=150)
        report_types = ("monthly",)
        page_desc = "Provincial overview of tourist arrivals received from LTCATO staff."

    return render_dashboard(
        "views/dashboard/pages/arrivals.html",
        user,
        reports=reports,
        report_types=report_types,
        lgus=list_lgus_simple() if role in ("super_admin", "lgu_admin") else [],
        page_title="Arrivals",
        page_description=page_desc,
        page_icon="bx-line-chart",
    )


@dashboard_bp.route("/accounts")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def accounts():
    user = get_current_dashboard_user()
    staff = list_profiles(role_key="ltcato_staff")
    lgu_users = list_profiles(role_key="lgu_admin")
    owners = list_profiles(role_key="establishment_owner")
    return render_dashboard(
        "views/dashboard/pages/accounts.html",
        user,
        staff_profiles=staff,
        lgu_profiles=lgu_users,
        owner_profiles=owners,
        lgus=list_lgus_simple(),
        page_title="Account management",
        page_description="Create and manage LTCATO staff and LGU portal accounts.",
        page_icon="bx-group",
    )


@dashboard_bp.route("/promotions")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def promotions():
    user = get_current_dashboard_user()
    if user["role"] == "super_admin":
        events = list_events(approval_status=None, limit=80)
        can_approve = True
        desc = "Review and approve events posted by LTCATO staff."
    else:
        events = list_events(approval_status=None, limit=80)
        can_approve = False
        desc = "Create provincial promotions and events for the public site."
    return render_dashboard(
        "views/dashboard/pages/promotions.html",
        user,
        events=events,
        can_approve=can_approve,
        lgus=list_lgus_simple(),
        page_title="Promotions & events",
        page_description=desc,
        page_icon="bx-calendar-event",
    )


@dashboard_bp.route("/chatbot")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def chatbot():
    user = get_current_dashboard_user()
    can_approve = user["role"] == "super_admin"
    entries = list_knowledge(approval_status=None if can_approve else None, limit=100)
    return render_dashboard(
        "views/dashboard/pages/chatbot.html",
        user,
        entries=entries,
        can_approve=can_approve,
        page_title="Chatbot configuration",
        page_description="FAQ knowledge base for the AI tourism assistant.",
        page_icon="bx-bot",
    )


@dashboard_bp.route("/feedback")
@dashboard_login_required
@role_required("super_admin", "lgu_admin")
def feedback():
    user = get_current_dashboard_user()
    lgu_id = _user_lgu_id(user) if user["role"] == "lgu_admin" else None
    items = list_feedbacks(lgu_id=lgu_id, limit=100)
    return render_dashboard(
        "views/dashboard/pages/feedback.html",
        user,
        feedbacks=items,
        page_title="Feedback",
        page_description="Tourist ratings and comments across managed establishments."
        if user["role"] == "lgu_admin"
        else "System-wide tourist feedback oversight.",
        page_icon="bx-message-square-dots",
    )


@dashboard_bp.route("/lgu-management")
@dashboard_login_required
@role_required("ltcato_staff")
def lgu_management():
    user = get_current_dashboard_user()
    pending = list_spots_for_dashboard(approval_status="pending_ltcato", limit=80)
    approved = list_spots_for_dashboard(approval_status="approved", limit=20)
    return render_dashboard(
        "views/dashboard/pages/lgu_management.html",
        user,
        pending_spots=pending,
        recent_approved=approved,
        page_title="LGU management",
        page_description="Confirm tourist spots approved by LGU tourism before publishing.",
        page_icon="bx-map",
    )


@dashboard_bp.route("/tourist-spots")
@dashboard_login_required
@role_required("lgu_admin")
def tourist_spots():
    user = get_current_dashboard_user()
    lgu_id = _user_lgu_id(user)
    spots = list_spots_for_dashboard(lgu_id=lgu_id, limit=100)
    return render_dashboard(
        "views/dashboard/pages/tourist_spots.html",
        user,
        spots=spots,
        page_title="Tourist spots",
        page_description="Establishments under your LGU — create owner accounts and manage listings.",
        page_icon="bx-map",
    )


@dashboard_bp.route("/site-updates")
@dashboard_login_required
@role_required("establishment_owner")
def site_updates():
    user = get_current_dashboard_user()
    spots = list_spots_for_dashboard(lgu_id=_user_lgu_id(user), limit=10)
    spot = spots[0] if spots else None
    return render_dashboard(
        "views/dashboard/pages/site_updates.html",
        user,
        spot=spot,
        page_title="Site updates",
        page_description="Update your establishment profile shown on the public portal.",
        page_icon="bx-store",
    )
