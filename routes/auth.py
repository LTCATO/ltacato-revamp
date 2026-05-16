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
                next_url = request.args.get("next") or url_for("public.home")
                return redirect(next_url)
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
        "full_name": "",
        "email": "",
        "phone": "",
        "country": "",
        "terms": False,
    }

    if request.method == "POST":
        full_name = _form_value("full_name")
        email = _form_value("email")
        phone = _form_value("phone")
        country = _form_value("country")
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        terms = request.form.get("terms") == "on"

        form_data = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "country": country,
            "terms": terms,
        }

        error = validate_register(full_name, email, password, confirm_password, terms)
        if error:
            flash(error, "danger")
        else:
            ok, auth_error, needs_confirmation = register_tourist(
                full_name, email, password, phone, country
            )
            if ok:
                if needs_confirmation:
                    flash(
                        "Account created! Check your email to confirm your address, then sign in.",
                        "success",
                    )
                    return redirect(url_for("auth.login"))
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
