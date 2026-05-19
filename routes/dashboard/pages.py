# pyrefly: ignore [missing-import]
from datetime import date
from io import BytesIO

from flask import flash, jsonify, redirect, request, send_file, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import (
    dashboard_login_required,
    render_dashboard,
    role_required,
)
from services.arrival_export import export_combined_workbook
from services.arrival_reports import (
    consolidate_establishment_reports,
    create_arrival_report,
    establishment_reports_for_lgu,
    list_arrival_reports,
    monthly_spot_reports_for_export,
)
from services.chatbot_knowledge import list_knowledge
from services.dashboard_analytics import (
    get_analytics_overview,
    get_establishment_analytics,
)
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
    role = user["role"]
    lgu_id = _user_lgu_id(user)

    if role == "establishment_owner":
        data = get_establishment_analytics(owner_id=user.get("id"))
        desc = "Visitor counts, feedback, and engagement metrics for your establishment."
    elif role == "lgu_admin":
        data = get_analytics_overview(lgu_id=lgu_id)
        desc = "Arrival data, spot performance, and feedback analytics for your LGU."
    elif role == "ltcato_staff":
        data = get_analytics_overview(lgu_id=None)
        desc = "Provincial tourism metrics across all LGUs, spots, and events."
    else:  # super_admin
        data = get_analytics_overview(lgu_id=None)
        desc = "System-wide KPIs: arrivals, spots, events, engagement, and tourist activity."

    return render_dashboard(
        "views/dashboard/pages/analytics.html",
        user,
        analytics=data,
        page_title="Analytics",
        page_description=desc,
        page_icon="bx-bar-chart-alt-2",
    )


@dashboard_bp.route("/decision-support")
@dashboard_login_required
def decision_support():
    from services.decision_support_service import (
        get_decision_support_data,
        get_lgu_decision_support_data,
        get_owner_decision_support_data,
        get_scraper_last_run,
    )

    user = get_current_dashboard_user()
    role = user["role"]
    lgu_id = _user_lgu_id(user)

    if role in ("super_admin", "ltcato_staff"):
        data = get_decision_support_data(lgu_id=None)
    elif role == "lgu_admin":
        if not lgu_id:
            from flask import flash, redirect, url_for
            flash("Your account is not linked to an LGU yet. Contact your administrator.", "warning")
            return redirect(url_for("dashboard.index"))
        data = get_lgu_decision_support_data(lgu_id)
    elif role == "establishment_owner":
        data = get_owner_decision_support_data(str(user.get("id") or ""))
    else:
        data = get_decision_support_data(lgu_id=None)

    last_run = get_scraper_last_run()
    return render_dashboard(
        "views/dashboard/pages/decision_support.html",
        user,
        ds=data,
        last_run=last_run,
        page_title="Decision Support",
        page_description="Data-driven insights and recommendations scoped to your role.",
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
        draft_records = list_arrival_reports(owner_id=user.get("id"), status="draft", limit=100)
        submitted_records = list_arrival_reports(owner_id=user.get("id"), status="submitted", limit=80)
        reports = draft_records + submitted_records
        reports.sort(key=lambda r: r.get("report_date") or "", reverse=True)
        report_types = ("daily", "weekly")
        page_desc = (
            "Save daily or weekly arrival records as drafts, then compile and submit "
            "them to your LGU Tourism Office when ready."
        )
        can_submit_day_tour = bool(spots)
        can_submit_overnight = bool(spots)
    elif role == "lgu_admin":
        draft_records = []
        submitted_records = []
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
        report_types = ()
        page_desc = (
            "Review establishment daily/weekly reports below, then use "
            "'Compile Monthly Report' to submit consolidated monthly totals to LTCATO."
        )
        can_submit_day_tour = False
        can_submit_overnight = False
    elif role == "ltcato_staff":
        draft_records = []
        submitted_records = []
        reports = list_arrival_reports(
            report_type="monthly", require_spot=True, limit=200
        )
        report_types = ()
        page_desc = (
            "Monthly per-spot arrivals from LGUs. Download Excel by municipality "
            "(all spots that reported)."
        )
    else:
        draft_records = []
        submitted_records = []
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

    # For establishment owners, pass draft/submitted split; others get a flat list
    if role == "establishment_owner":
        template_draft_records = draft_records
        template_submitted_records = submitted_records
    else:
        template_draft_records = []
        template_submitted_records = []

    return render_dashboard(
        "views/dashboard/pages/arrivals.html",
        user,
        reports=reports,
        draft_records=template_draft_records,
        submitted_records=template_submitted_records,
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


@dashboard_bp.route("/arrivals/consolidate")
@dashboard_login_required
@role_required("lgu_admin")
def arrivals_consolidate():
    """
    Preview page: shows aggregated establishment reports for a chosen month
    so the LGU admin can review and submit the consolidated monthly totals.
    """
    user = get_current_dashboard_user()
    lgu_id = _user_lgu_id(user)
    if not lgu_id:
        flash("Your account is not linked to an LGU yet.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    year_raw = request.args.get("year", "")
    month_raw = request.args.get("month", "")
    today = date.today()
    try:
        year = int(year_raw) if year_raw else today.year
        month = int(month_raw) if month_raw else today.month
        if not (1 <= month <= 12):
            raise ValueError
    except ValueError:
        year, month = today.year, today.month

    day_tour_rows = consolidate_establishment_reports(
        lgu_id, year=year, month=month, visitor_category="day_tour"
    )
    overnight_rows = consolidate_establishment_reports(
        lgu_id, year=year, month=month, visitor_category="overnight"
    )

    # Build year/month options for the picker (current year ± 1)
    month_options = [
        {"year": y, "month": m, "label": f"{date(y, m, 1).strftime('%B %Y')}"}
        for y in range(today.year - 1, today.year + 1)
        for m in range(1, 13)
        if date(y, m, 1) <= today
    ]

    return render_dashboard(
        "views/dashboard/pages/arrivals_consolidate.html",
        user,
        year=year,
        month=month,
        month_label=date(year, month, 1).strftime("%B %Y"),
        day_tour_rows=day_tour_rows,
        overnight_rows=overnight_rows,
        month_options=month_options,
        page_title="Compile Monthly Arrivals",
        page_description=(
            "Review establishment reports for the selected month, then submit "
            "the consolidated monthly totals to LTCATO."
        ),
        page_icon="bx-calendar-check",
    )


@dashboard_bp.route("/arrivals/consolidate/submit", methods=["POST"])
@dashboard_login_required
@role_required("lgu_admin")
def arrivals_consolidate_submit():
    """
    Submit consolidated monthly arrival totals (one row per spot) to LTCATO.
    Reads pre-aggregated data from hidden form fields — no manual re-entry.
    """
    from calendar import monthrange

    user = get_current_dashboard_user()
    lgu_id = _user_lgu_id(user)
    if not lgu_id:
        flash("Your account is not linked to an LGU yet.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    year_raw = request.form.get("year", "")
    month_raw = request.form.get("month", "")
    visitor_category = request.form.get("visitor_category", "")
    if visitor_category not in ("day_tour", "overnight"):
        flash("Invalid visitor category.", "danger")
        return redirect(url_for("dashboard.arrivals_consolidate"))

    try:
        year = int(year_raw)
        month = int(month_raw)
        if not (1 <= month <= 12):
            raise ValueError
    except ValueError:
        flash("Invalid year or month.", "danger")
        return redirect(url_for("dashboard.arrivals_consolidate"))

    # Re-aggregate from DB to avoid tampering via hidden fields
    rows = consolidate_establishment_reports(
        lgu_id, year=year, month=month, visitor_category=visitor_category
    )
    if not rows:
        flash(
            f"No establishment reports found for {date(year, month, 1).strftime('%B %Y')} "
            f"({'day tour' if visitor_category == 'day_tour' else 'overnight'}). "
            "Nothing to submit.",
            "warning",
        )
        return redirect(url_for("dashboard.arrivals_consolidate", year=year, month=month))

    # Use the last day of the month as the report date
    last_day = date(year, month, monthrange(year, month)[1])
    submitted = 0
    errors = 0
    for row in rows:
        payload = {
            "tourist_spot_id": row["tourist_spot_id"],
            "lgu_id": lgu_id,
            "submitted_by": user.get("id"),
            "report_type": "monthly",
            "report_date": last_day.isoformat(),
            "visitor_category": visitor_category,
            "overnight_nights": row.get("overnight_nights", 0),
            **{k: row.get(k, 0) for k in (
                "this_city_male", "this_city_female",
                "other_city_male", "other_city_female",
                "other_province_male", "other_province_female",
                "foreign_male", "foreign_female",
            )},
        }
        try:
            create_arrival_report(payload)
            submitted += 1
        except Exception:
            errors += 1

    category_label = "day tour" if visitor_category == "day_tour" else "overnight"
    month_label = date(year, month, 1).strftime("%B %Y")
    if submitted:
        flash(
            f"Submitted {submitted} consolidated {category_label} report(s) for {month_label} to LTCATO.",
            "success",
        )
    if errors:
        flash(f"{errors} spot(s) could not be saved. Please try again.", "danger")

    return redirect(url_for("dashboard.arrivals"))


@dashboard_bp.route("/arrivals/export")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def arrivals_export():
    lgu_raw = request.args.get("lgu_id")
    date_raw = request.args.get("report_date")
    if not lgu_raw or not str(lgu_raw).isdigit():
        flash("Select an LGU to download its arrival Excel report.", "warning")
        return redirect(url_for("dashboard.arrivals"))
    lgu_id = int(lgu_raw)
    report_date = date.fromisoformat(date_raw) if date_raw else None

    data, filename = export_combined_workbook(lgu_id=lgu_id, report_date=report_date)

    if not monthly_spot_reports_for_export(lgu_id=lgu_id, report_date=report_date):
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
    events = list_events(approval_status=None, limit=80)
    return render_dashboard(
        "views/dashboard/pages/promotions.html",
        user,
        events=events,
        lgus=list_lgus_simple(),
        page_title="Promotions & events",
        page_description="Create and manage provincial promotions and events for the public site.",
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
        subcategories_by_category=subcategories_grouped_by_category()
        if categories
        else {},
        claimable_spots=claimable_spots,
        page_title="Site updates",
        page_description="Claim, register, or update your establishment on the public portal.",
        page_icon="bx-store",
    )
