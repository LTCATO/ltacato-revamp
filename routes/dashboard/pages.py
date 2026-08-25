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
    create_arrival_report,
    list_arrival_reports,
    monthly_spot_reports_for_export,
)
from services.chatbot_knowledge import list_knowledge
from services.chatbot_unanswered import list_unanswered_queries
from services.dashboard_analytics import (
    get_analytics_overview,
    get_establishment_analytics,
)
from services.dashboard_auth import get_current_dashboard_user, resolve_dashboard_lgu_id
from services.dashboard_pages import get_dashboard_overview, get_workflow_cards
from services.events import _compute_event_status, list_events
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


def _paginate_reports_by_year(
    rows: list[dict], page: int
) -> tuple[list[dict], str, bool]:
    """Page 1 = the current calendar year; each higher page number goes one
    year further into the past. The target year is computed fresh from
    today's date on every request (nothing is stored), so once a new year
    starts, what used to be page 1 automatically becomes page 2. These rows
    are already one-per-month (monthly submissions), so pagination here is
    by year rather than by month."""
    today = date.today()
    target_year = today.year - (page - 1)
    prefix = f"{target_year:04d}"
    page_rows = [r for r in rows if str(r.get("report_date") or "").startswith(prefix)]
    has_older = any(str(r.get("report_date") or "")[:4] < prefix for r in rows)
    return page_rows, str(target_year), has_older


def _month_range_for_page(live_page: int) -> tuple[str, str, str]:
    """Page 1 = the current calendar month; each higher page goes one month
    further into the past. Returns (date_from, date_to, month_label) for
    that whole month, computed fresh from today's date every request."""
    from calendar import monthrange

    today = date.today()
    total_months = today.year * 12 + (today.month - 1) - (live_page - 1)
    target_year, target_month = divmod(total_months, 12)
    target_month += 1
    last_day = monthrange(target_year, target_month)[1]
    date_from = date(target_year, target_month, 1).isoformat()
    date_to = date(target_year, target_month, last_day).isoformat()
    month_label = date(target_year, target_month, 1).strftime("%B %Y")
    return date_from, date_to, month_label


@dashboard_bp.route("/arrivals")
@dashboard_login_required
def arrivals():
    from services.visit_schedules import (
        aggregate_visits_by_day,
        aggregate_visits_by_spot,
        list_completed_visits,
    )

    user = get_current_dashboard_user()
    role = user["role"]
    lgu_id = _user_lgu_id(user)

    can_download = role in ("super_admin", "ltcato_staff")
    spots: list = []
    reports: list = []
    monthly_rows: list = []
    live_day_tour_rows: list = []
    live_overnight_rows: list = []
    live_daily_breakdown: list = []

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    page_year_label = ""
    has_older_page = False

    # The day tour / overnight live view pages through whole calendar months
    # (page 1 = current month). An explicit date_from/date_to in the query
    # string overrides the page nav for a custom range.
    live_page = request.args.get("live_page", 1, type=int)
    if live_page < 1:
        live_page = 1
    explicit_range = bool(request.args.get("date_from") or request.args.get("date_to"))
    if explicit_range:
        live_date_from = request.args.get("date_from") or date.today().isoformat()
        live_date_to = request.args.get("date_to") or live_date_from
        if live_date_to < live_date_from:
            live_date_from, live_date_to = live_date_to, live_date_from
        live_month_label = ""
    else:
        live_date_from, live_date_to, live_month_label = _month_range_for_page(live_page)

    if role == "establishment_owner":
        spots = list_spots_for_dashboard(owner_id=user.get("id"), limit=20)
        spot_ids = [int(s["id"]) for s in spots if s.get("id") is not None]
        live_rows = (
            list_completed_visits(spot_ids=spot_ids, date_from=live_date_from, date_to=live_date_to)
            if spot_ids
            else []
        )
        live_day_tour_rows = aggregate_visits_by_spot(
            [r for r in live_rows if r.get("visitor_category") != "overnight"]
        )
        live_overnight_rows = aggregate_visits_by_spot(
            [r for r in live_rows if r.get("visitor_category") == "overnight"]
        )
        live_daily_breakdown = aggregate_visits_by_day(
            live_rows, date_from=live_date_from, date_to=live_date_to
        )
        page_desc = (
            "Visitor activity from your Logs is automatically included here — no report "
            "generation needed. Add walk-ins or edit demographics from the Logs page."
        )
    elif role == "lgu_admin":
        spots = list_spots_for_dashboard(lgu_id=lgu_id, limit=200) if lgu_id else []
        live_rows = (
            list_completed_visits(lgu_id=lgu_id, date_from=live_date_from, date_to=live_date_to)
            if lgu_id
            else []
        )
        live_day_tour_rows = aggregate_visits_by_spot(
            [r for r in live_rows if r.get("visitor_category") != "overnight"]
        )
        live_overnight_rows = aggregate_visits_by_spot(
            [r for r in live_rows if r.get("visitor_category") == "overnight"]
        )
        live_daily_breakdown = aggregate_visits_by_day(
            live_rows, date_from=live_date_from, date_to=live_date_to
        )
        all_monthly_rows = (
            list_arrival_reports(
                lgu_id=lgu_id, report_type="monthly", require_spot=True, limit=1000
            )
            if lgu_id
            else []
        )
        monthly_rows, page_year_label, has_older_page = _paginate_reports_by_year(
            all_monthly_rows, page
        )
        page_desc = (
            "Visitor activity is aggregated automatically from establishment logs — pick a "
            "date range to review it, then use 'Compile Monthly Report' to submit validated "
            "monthly totals to LTCATO."
        )
    elif role == "ltcato_staff":
        all_reports = list_arrival_reports(
            report_type="monthly", require_spot=True, limit=1000
        )
        reports, page_year_label, has_older_page = _paginate_reports_by_year(
            all_reports, page
        )
        page_desc = (
            "Monthly per-spot arrivals from LGUs. Download Excel by municipality "
            "(all spots that reported)."
        )
    else:
        all_reports = list_arrival_reports(
            report_type="monthly", require_spot=True, limit=1000
        )
        reports, page_year_label, has_older_page = _paginate_reports_by_year(
            all_reports, page
        )
        page_desc = (
            "Provincial oversight of monthly per-spot arrivals. Download Excel by LGU."
        )

    export_lgus = list_lgus_simple() if can_download else []
    needs_lgu_selection = role == "lgu_admin" and not lgu_id

    return render_dashboard(
        "views/dashboard/pages/arrivals.html",
        user,
        reports=reports,
        monthly_rows=monthly_rows,
        live_day_tour_rows=live_day_tour_rows,
        live_overnight_rows=live_overnight_rows,
        live_daily_breakdown=live_daily_breakdown,
        live_date_from=live_date_from,
        live_date_to=live_date_to,
        live_page=live_page,
        live_month_label=live_month_label,
        report_page=page,
        page_year_label=page_year_label,
        has_older_page=has_older_page,
        spots=spots,
        lgus=export_lgus,
        needs_lgu_selection=needs_lgu_selection,
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

    from services.visit_schedules import consolidate_lgu_visits_for_month

    day_tour_rows = consolidate_lgu_visits_for_month(
        lgu_id, year=year, month=month, visitor_category="day_tour"
    )
    overnight_rows = consolidate_lgu_visits_for_month(
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
    from services.visit_schedules import consolidate_lgu_visits_for_month

    rows = consolidate_lgu_visits_for_month(
        lgu_id, year=year, month=month, visitor_category=visitor_category
    )
    if not rows:
        flash(
            f"No visitor activity found for {date(year, month, 1).strftime('%B %Y')} "
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
            "status": "submitted",
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

    # Check for data BEFORE generating the file: flashing a message and then
    # still send_file()-ing left the warning stranded in the session (it can
    # only render on the *next* full page load, not this download response),
    # which looked like "a warning appeared instead of the download." Now
    # it's one or the other, cleanly: no data -> redirect with the message,
    # no leftover flash; data exists -> the file downloads with nothing else.
    if not monthly_spot_reports_for_export(lgu_id=lgu_id, report_date=report_date):
        flash(
            "No monthly per-spot reports for this LGU yet — LGU officers must submit "
            "monthly data per tourist spot before an Excel report can be generated.",
            "info",
        )
        return redirect(url_for("dashboard.arrivals"))

    data, filename = export_combined_workbook(lgu_id=lgu_id, report_date=report_date)

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
@role_required("super_admin", "ltcato_staff", "lgu_admin")
def promotions():
    user = get_current_dashboard_user()
    forced_lgu_id = None
    if user["role"] == "lgu_admin":
        forced_lgu_id = _user_lgu_id(user)
        events = list_events(lgu_id=forced_lgu_id, approval_status=None, limit=80)
    else:
        events = list_events(approval_status=None, limit=80)
    for event in events:
        event["computed_status"] = _compute_event_status(event)
    return render_dashboard(
        "views/dashboard/pages/promotions.html",
        user,
        events=events,
        lgus=list_lgus_simple(),
        forced_lgu_id=forced_lgu_id,
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
    entries = list_knowledge(approval_status=None, limit=100)
    unanswered = list_unanswered_queries(resolved=False, limit=100)
    return render_dashboard(
        "views/dashboard/pages/chatbot.html",
        user,
        entries=entries,
        unanswered=unanswered,
        can_approve=can_approve,
        page_title="Chatbot configuration",
        page_description="Manage the FAQ knowledge base for the LARA AI tourism assistant.",
        page_icon="bx-bot",
    )


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@dashboard_login_required
def manage_profile():
    from services.profiles import get_dashboard_profile, update_dashboard_profile
    from supabase import create_client
    import os

    user = get_current_dashboard_user()
    profile = get_dashboard_profile(str(user["id"]))

    if request.method == "POST":
        action = request.form.get("action", "profile")

        if action == "profile":
            ok, err = update_dashboard_profile(
                str(user["id"]),
                first_name=request.form.get("first_name", ""),
                last_name=request.form.get("last_name", ""),
                middle_name=request.form.get("middle_name", ""),
                position=request.form.get("position", ""),
            )
            if ok:
                # Refresh session name
                first = request.form.get("first_name", "").strip()
                last = request.form.get("last_name", "").strip()
                from flask import session as _session
                _session["dashboard_name"] = f"{first} {last}".strip() or user["name"]
                flash("Profile updated successfully.", "success")
            else:
                flash(err or "Could not update profile.", "danger")
            return redirect(url_for("dashboard.manage_profile"))

        elif action == "password":
            current_pw = request.form.get("current_password", "").strip()
            new_pw = request.form.get("new_password", "").strip()
            confirm_pw = request.form.get("confirm_password", "").strip()

            if not current_pw or not new_pw or not confirm_pw:
                flash("All password fields are required.", "danger")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "danger")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "danger")
            else:
                # Verify current password by attempting sign-in
                url = os.getenv("SUPABASE_URL")
                anon_key = os.getenv("SUPABASE_KEY")
                try:
                    temp_client = create_client(url, anon_key)
                    temp_client.auth.sign_in_with_password(
                        {"email": user["email"], "password": current_pw}
                    )
                    # Current password is correct — update via admin API
                    from services.supabase_client import get_supabase
                    get_supabase().auth.admin.update_user_by_id(
                        str(user["id"]), {"password": new_pw}
                    )
                    flash("Password changed successfully.", "success")
                except Exception as exc:
                    err_str = str(exc).lower()
                    if "invalid" in err_str or "credentials" in err_str or "password" in err_str:
                        flash("Current password is incorrect.", "danger")
                    else:
                        flash(f"Could not change password: {exc}", "danger")
            return redirect(url_for("dashboard.manage_profile"))

    return render_dashboard(
        "views/dashboard/pages/profile.html",
        user,
        profile=profile,
        page_title="My profile",
        page_description="Update your personal details and change your password.",
        page_icon="bx-user-circle",
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


@dashboard_bp.route("/visit-schedule")
@dashboard_login_required
@role_required("establishment_owner")
def visit_schedules():
    from services.visit_schedules import list_logs_for_owner, list_visits_for_owner

    user = get_current_dashboard_user()
    visits = list_visits_for_owner(str(user.get("id")), limit=200)

    q = request.args.get("q") or None
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    logs = list_logs_for_owner(str(user.get("id")), q=q, date_from=date_from, date_to=date_to)
    spots = list_spots_for_dashboard(owner_id=user.get("id"), limit=20)

    return render_dashboard(
        "views/dashboard/pages/visit_schedules.html",
        user,
        visits=visits,
        logs=logs,
        spots=spots,
        q=q or "",
        date_from=date_from or "",
        date_to=date_to or "",
        page_title="Visit schedule",
        page_description="Manage visit requests and browse logs — activity here is automatically "
        "included in your LGU's arrival reporting.",
        page_icon="bx-calendar-check",
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
    spots = list_spots_for_dashboard(owner_id=user.get("id"), limit=20)
    lgu_id = _user_lgu_id(user)
    claimable_spots = list_claimable_spots_for_lgu(lgu_id, limit=100) if lgu_id else []
    categories = get_categories()
    return render_dashboard(
        "views/dashboard/pages/site_updates.html",
        user,
        spots=spots,
        categories=categories,
        subcategories_by_category=subcategories_grouped_by_category(),
        claimable_spots=claimable_spots,
        page_title="Site updates",
        page_description="Claim, register, or update your establishments on the public portal.",
        page_icon="bx-store",
    )
