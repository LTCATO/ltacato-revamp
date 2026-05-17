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
            next_url = request.url
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped
