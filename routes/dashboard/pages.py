# pyrefly: ignore [missing-import]
from datetime import date

from io import BytesIO

from flask import flash, jsonify, redirect, request, send_file, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required, render_dashboard, role_required
from services.arrival_export import export_day_tour_workbook, export_overnight_workbook
from services.arrival_reports import (
    establishment_reports_for_lgu,
    list_arrival_reports,
    monthly_spot_reports_for_export,
)
from services.chatbot_knowledge import list_knowledge
from services.dashboard_analytics import get_analytics_overview, get_establishment_analytics
from services.dashboard_auth import get_current_dashboard_user, resolve_dashboard_lgu_id
from services.dashboard_pages import get_dashboard_overview, get_workflow_cards
from services.events import list_events
from services.external_reviews import list_external_reviews
from services.feedbacks import list_feedbacks
from services.lgus import list_lgus_simple
from services.profiles import list_profiles
from services.spots import (
    get_categories,
    get_subcategories,
    list_claimable_spots_for_lgu,
    list_spots_for_dashboard,
    subcategories_grouped_by_category,
)


def _user_lgu_id(user: dict) -> int | None:
    return resolve_dashboard_lgu_id(user)


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
        data = get_establishment_analytics(owner_id=user.get("id"))
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

    can_submit_day_tour = False
    can_submit_overnight = False
    can_download = role in ("super_admin", "ltcato_staff")
    spots: list = []

    if role == "establishment_owner":
        spots = list_spots_for_dashboard(owner_id=user.get("id"), limit=20)
        reports = list_arrival_reports(owner_id=user.get("id"), limit=80)
        report_types = ("daily", "weekly")
        page_desc = "Submit daily or weekly visitor counts (day tour and overnight) to your LGU."
        can_submit_day_tour = bool(spots)
        can_submit_overnight = bool(spots)
    elif role == "lgu_admin":
        spots = list_spots_for_dashboard(lgu_id=lgu_id, limit=200) if lgu_id else []
        establishment_rows = establishment_reports_for_lgu(lgu_id) if lgu_id else []
        monthly_rows = (
            list_arrival_reports(
                lgu_id=lgu_id, report_type="monthly", require_spot=True, limit=100
            )
            if lgu_id
            else []
        )
        reports = establishment_rows + monthly_rows
        reports.sort(key=lambda r: r.get("report_date") or "", reverse=True)
        report_types = ("monthly",)
        page_desc = (
            "Review establishment daily/weekly reports, then submit monthly totals "
            "per tourist spot in your LGU to LTCATO staff."
        )
        can_submit_day_tour = bool(spots)
        can_submit_overnight = bool(spots)
    elif role == "ltcato_staff":
        reports = list_arrival_reports(
            report_type="monthly", require_spot=True, limit=200
        )
        report_types = ()
        page_desc = (
            "Monthly per-spot arrivals from LGUs. Download Excel by municipality "
            "(all spots that reported)."
        )
    else:
        reports = list_arrival_reports(
            report_type="monthly", require_spot=True, limit=250
        )
        report_types = ()
        page_desc = (
            "Provincial oversight of monthly per-spot arrivals. Download Excel by LGU."
        )

    export_lgus = list_lgus_simple() if can_download else []
    needs_lgu_selection = role == "lgu_admin" and not lgu_id
    lgu_picker_list = list_lgus_simple() if needs_lgu_selection else []

    return render_dashboard(
        "views/dashboard/pages/arrivals.html",
        user,
        reports=reports,
        report_types=report_types,
        spots=spots,
        lgus=export_lgus,
        lgu_picker_list=lgu_picker_list,
        needs_lgu_selection=needs_lgu_selection,
        can_submit_day_tour=can_submit_day_tour,
        can_submit_overnight=can_submit_overnight,
        can_download=can_download,
        page_title="Arrivals",
        page_description=page_desc,
        page_icon="bx-line-chart",
    )


@dashboard_bp.route("/arrivals/export/<category>")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def arrivals_export(category: str):
    lgu_raw = request.args.get("lgu_id")
    date_raw = request.args.get("report_date")
    if not lgu_raw or not str(lgu_raw).isdigit():
        flash("Select an LGU to download its arrival Excel report.", "warning")
        return redirect(url_for("dashboard.arrivals"))
    lgu_id = int(lgu_raw)
    report_date = date.fromisoformat(date_raw) if date_raw else None

    export_category = "day_tour" if category == "day_tour" else "overnight"
    if category == "day_tour":
        data, filename = export_day_tour_workbook(lgu_id=lgu_id, report_date=report_date)
    elif category == "overnight":
        data, filename = export_overnight_workbook(lgu_id=lgu_id, report_date=report_date)
    else:
        flash("Unknown export type.", "warning")
        return redirect(url_for("dashboard.arrivals"))

    if not monthly_spot_reports_for_export(
        lgu_id=lgu_id, report_date=report_date, visitor_category=export_category
    ):
        flash(
            "No monthly per-spot reports for this LGU yet. "
            "LGU officers must submit monthly data per tourist spot.",
            "info",
        )

    return send_file(
        BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
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
        page_description="Establishments under your LGU — create owner accounts; owners register their own spots.",
        page_icon="bx-map",
    )


@dashboard_bp.route("/api/attraction-subcategories")
@dashboard_login_required
def attraction_subcategories_api():
    category_raw = request.args.get("category_id", "").strip()
    if not category_raw.isdigit():
        return jsonify([])
    return jsonify(get_subcategories(category_id=int(category_raw)))


@dashboard_bp.route("/site-updates")
@dashboard_login_required
@role_required("establishment_owner")
def site_updates():
    user = get_current_dashboard_user()
    spots = list_spots_for_dashboard(owner_id=user.get("id"), limit=10)
    spot = spots[0] if spots else None
    lgu_id = _user_lgu_id(user)
    claimable_spots = (
        list_claimable_spots_for_lgu(lgu_id, limit=100) if lgu_id and not spot else []
    )
    categories = get_categories() if not spot else []
    return render_dashboard(
        "views/dashboard/pages/site_updates.html",
        user,
        spot=spot,
        categories=categories,
        subcategories_by_category=subcategories_grouped_by_category() if categories else {},
        claimable_spots=claimable_spots,
        page_title="Site updates",
        page_description="Claim, register, or update your establishment on the public portal.",
        page_icon="bx-store",
    )
