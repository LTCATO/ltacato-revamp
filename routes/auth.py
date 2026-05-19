# pyrefly: ignore [missing-import]
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.tourist_auth import (
    TOURIST_BENEFITS,
    get_current_tourist,
    login_tourist,
    logout_tourist,
    register_tourist,
    validate_login,
    validate_register,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _form_value(key: str, default: str = "") -> str:
    return (request.form.get(key) or default).strip()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_tourist():
        next_url = request.args.get("next") or ""
        # Only follow relative paths to prevent open-redirect attacks
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("public.home"))

    form_data = {"email": "", "remember": False}

    if request.method == "POST":
        email = _form_value("email")
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "on"
        form_data = {"email": email, "remember": remember}

        error = validate_login(email, password)
        if error:
            flash(error, "danger")
        else:
            ok, auth_error = login_tourist(email, password)
            if ok:
                session.permanent = remember
                flash("Welcome back! You are signed in as a tourist.", "success")
                next_url = request.args.get("next") or ""
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect(url_for("public.home"))
            flash(auth_error or "Sign in failed.", "danger")

    return render_template(
        "views/auth/login.html",
        benefits=TOURIST_BENEFITS,
        form_data=form_data,
    )


@auth_bp.route("/register", methods=["GET", "POST"])
@auth_bp.route("/signup", methods=["GET", "POST"])
def register():
    if get_current_tourist():
        return redirect(url_for("public.home"))

    form_data = {
        "first_name": "",
        "middle_name": "",
        "last_name": "",
        "email": "",
        "terms": False,
    }

    if request.method == "POST":
        first_name = _form_value("first_name")
        middle_name = _form_value("middle_name")
        last_name = _form_value("last_name")
        email = _form_value("email")
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        terms = request.form.get("terms") == "on"

        form_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "email": email,
            "terms": terms,
        }

        error = validate_register(first_name, last_name, email, password, confirm_password, terms)
        if error:
            flash(error, "danger")
        else:
            ok, auth_error, needs_confirmation = register_tourist(
                first_name, last_name, email, password, middle_name
            )
            if ok:
                if needs_confirmation:
                    return render_template(
                        "views/auth/register.html",
                        benefits=TOURIST_BENEFITS,
                        form_data=form_data,
                        show_confirmation_modal=True,
                        registered_email=email,
                    )
                flash("Welcome to LTCATO! Your tourist account is ready.", "success")
                return redirect(url_for("public.home"))
            flash(auth_error or "Registration failed.", "danger")

    return render_template(
        "views/auth/register.html",
        benefits=TOURIST_BENEFITS,
        form_data=form_data,
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_tourist()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
