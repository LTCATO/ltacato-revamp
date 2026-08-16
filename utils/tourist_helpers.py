"""Decorators and helpers for tourist-only routes."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import flash, redirect, request, url_for

from services.tourist_auth import get_current_tourist


def tourist_login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_tourist():
            flash("Please sign in to save trips and manage your profile.", "warning")
            # Use relative path to avoid open-redirect issues with absolute URLs
            next_path = request.path
            if request.query_string:
                next_path = f"{request.path}?{request.query_string.decode()}"
            return redirect(url_for("auth.login", next=next_path))
        return view(*args, **kwargs)

    return wrapped
