# pyrefly: ignore [missing-import]
from flask import Blueprint, flash, redirect, render_template, request, url_for

from services.dashboard_auth import (
    dashboard_login_required,
    get_current_dashboard_user,
    get_dashboard_overview,
    get_demo_accounts,
    get_nav_items,
    get_workflow_cards,
    login_dashboard,
    logout_dashboard,
)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _form_email() -> str:
    return (request.form.get("email") or "").strip()


@dashboard_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_dashboard_user():
        return redirect(url_for("dashboard.index"))

    form_data = {"email": ""}

    if request.method == "POST":
        email = _form_email()
        password = request.form.get("password") or ""
        form_data = {"email": email}

        if not email or not password:
            flash("Email and password are required.", "danger")
        else:
            ok, error = login_dashboard(email, password)
            if ok:
                flash("Welcome to the LTCATO dashboard.", "success")
                next_url = request.args.get("next") or url_for("dashboard.index")
                return redirect(next_url)
            flash(error or "Sign in failed.", "danger")

    return render_template(
        "views/auth/dashboard-login.html",
        form_data=form_data,
        demo_accounts=get_demo_accounts(),
    )


@dashboard_bp.route("/logout", methods=["POST"])
def logout():
    logout_dashboard()
    flash("You have been signed out of the dashboard.", "info")
    return redirect(url_for("dashboard.login"))


@dashboard_bp.route("/")
@dashboard_login_required
def index():
    user = get_current_dashboard_user()
    role = user["role"]
    overview = get_dashboard_overview(role)
    workflow_cards = get_workflow_cards(role)
    for i, card in enumerate(workflow_cards):
        if i < len(overview["quick_actions"]):
            card["endpoint"] = overview["quick_actions"][i]["endpoint"]
    return render_template(
        "views/dashboard/index.html",
        user=user,
        overview=overview,
        workflow_cards=workflow_cards,
        nav_items=get_nav_items(role),
    )


def _stub_page(title: str, description: str, icon: str = "bx-wrench"):
    user = get_current_dashboard_user()
    return render_template(
        "views/dashboard/stub.html",
        user=user,
        nav_items=get_nav_items(user["role"]),
        page_title=title,
        page_description=description,
        page_icon=icon,
    )


@dashboard_bp.route("/arrivals")
@dashboard_login_required
def arrivals():
    return _stub_page(
        "Tourist arrivals",
        "Receive monthly LGU reports and track provincial visitor statistics.",
        "bx-line-chart",
    )


@dashboard_bp.route("/reports")
@dashboard_login_required
def reports():
    return _stub_page("Reports", "Analytics and export tools for tourism data.", "bx-bar-chart-alt-2")


@dashboard_bp.route("/events")
@dashboard_login_required
def events():
    return _stub_page(
        "Events & promotion",
        "Create and manage provincial events such as Anilag for the public site.",
        "bx-calendar-event",
    )


@dashboard_bp.route("/spots")
@dashboard_login_required
def spots():
    return _stub_page(
        "Tourist spots",
        "Oversee verified destinations shown on the public portal.",
        "bx-map",
    )


@dashboard_bp.route("/accounts")
@dashboard_login_required
def accounts():
    return _stub_page(
        "Account management",
        "Manage LGU, establishment, staff, and tourist accounts.",
        "bx-group",
    )


@dashboard_bp.route("/settings")
@dashboard_login_required
def settings():
    return _stub_page("Settings", "System configuration and office preferences.", "bx-cog")


@dashboard_bp.route("/staff-accounts")
@dashboard_login_required
def staff_accounts():
    return _stub_page(
        "Staff accounts",
        "Manage establishment staff who submit daily or weekly arrivals.",
        "bx-user",
    )


@dashboard_bp.route("/establishments")
@dashboard_login_required
def establishments():
    return _stub_page(
        "Establishments",
        "View establishments under your LGU jurisdiction.",
        "bx-buildings",
    )


@dashboard_bp.route("/monthly-report")
@dashboard_login_required
def monthly_report():
    return _stub_page(
        "Monthly report to LTCATO",
        "Compile and submit monthly tourist arrival totals to the provincial office.",
        "bx-send",
    )


@dashboard_bp.route("/my-establishment")
@dashboard_login_required
def my_establishment():
    return _stub_page(
        "My establishment",
        "Edit and update your establishment profile on the public directory.",
        "bx-store",
    )


@dashboard_bp.route("/submit-arrivals")
@dashboard_login_required
def submit_arrivals():
    return _stub_page(
        "Submit arrivals",
        "Pass daily or weekly visitor counts to your LGU.",
        "bx-edit",
    )


@dashboard_bp.route("/arrival-history")
@dashboard_login_required
def arrival_history():
    return _stub_page(
        "Submission history",
        "View past daily and weekly arrival submissions.",
        "bx-history",
    )
