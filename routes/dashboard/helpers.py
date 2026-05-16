from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import abort, flash, redirect, render_template, url_for

from services.dashboard_auth import get_current_dashboard_user, get_nav_items, request_path


def dashboard_login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_dashboard_user():
            flash("Please sign in to access the dashboard.", "warning")
            return redirect(url_for("dashboard.login", next=request_path()))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view: Callable):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_dashboard_user()
            if not user:
                return redirect(url_for("dashboard.login"))
            if user["role"] not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("dashboard.index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def render_dashboard(template: str, user: dict, **context):
    role = user["role"]
    context.setdefault("user", user)
    context.setdefault("nav_items", get_nav_items(role))
    return render_template(template, **context)
