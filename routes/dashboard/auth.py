from flask import flash, redirect, render_template, request, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required
from services.dashboard_auth import (
    get_current_dashboard_user,
    login_dashboard,
    logout_dashboard,
    request_path,
)


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
    )


@dashboard_bp.route("/logout", methods=["POST"])
def logout():
    logout_dashboard()
    flash("You have been signed out of the dashboard.", "info")
    return redirect(url_for("dashboard.login"))
