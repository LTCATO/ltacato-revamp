"""
Tourist-only authentication via Supabase Auth.
"""

from __future__ import annotations

import re
from typing import Any

# pyrefly: ignore [missing-import]
from flask import session
# pyrefly: ignore [missing-import]
from supabase_auth.errors import AuthApiError

from services.supabase_client import get_supabase

TOURIST_ROLE = "tourist"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

SESSION_KEYS = (
    "tourist_id",
    "tourist_email",
    "tourist_name",
    "tourist_access_token",
)

TOURIST_BENEFITS: list[dict[str, str]] = [
    {
        "icon": "ph-bookmark-simple",
        "title": "Save favorite spots",
        "text": "Bookmark destinations across Laguna and build your personal travel list.",
    },
    {
        "icon": "ph-calendar-dots",
        "title": "Plan your itinerary",
        "text": "Organize day trips, events, and routes before you arrive in the province.",
    },
    {
        "icon": "ph-star",
        "title": "Share honest reviews",
        "text": "Help fellow travelers with feedback on places you have visited.",
    },
    {
        "icon": "ph-robot",
        "title": "Lara travel assistant",
        "text": "Get trip ideas and answers tailored to Laguna's towns, food, and culture.",
    },
]


def get_current_tourist() -> dict[str, str] | None:
    tourist_id = session.get("tourist_id")
    if not tourist_id:
        return None
    return {
        "id": tourist_id,
        "email": session.get("tourist_email", ""),
        "name": session.get("tourist_name", "Traveler"),
    }


def _user_metadata(user: Any) -> dict[str, Any]:
    return getattr(user, "user_metadata", None) or {}


def _is_tourist(user: Any) -> bool:
    return _user_metadata(user).get("role") == TOURIST_ROLE


def _set_session(user: Any, auth_session: Any = None) -> None:
    meta = _user_metadata(user)
    session["tourist_id"] = user.id
    session["tourist_email"] = user.email or ""
    
    first_name = meta.get("first_name") or ""
    last_name = meta.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip()
    session["tourist_name"] = full_name or (user.email or "Traveler").split("@")[0]
    
    if auth_session and getattr(auth_session, "access_token", None):
        session["tourist_access_token"] = auth_session.access_token


def logout_tourist() -> None:
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in SESSION_KEYS:
        session.pop(key, None)


def validate_login(email: str, password: str) -> str | None:
    email = (email or "").strip().lower()
    password = password or ""
    if not email:
        return "Email address is required."
    if not EMAIL_PATTERN.match(email):
        return "Enter a valid email address."
    if not password:
        return "Password is required."
    return None


def validate_register(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    confirm_password: str,
    terms: bool,
) -> str | None:
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    confirm_password = confirm_password or ""

    if len(first_name) < 2:
        return "Please enter your first name."
    if len(last_name) < 2:
        return "Please enter your last name."
    if not email:
        return "Email address is required."
    if not EMAIL_PATTERN.match(email):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password != confirm_password:
        return "Passwords do not match."
    if not terms:
        return "You must accept the terms to create a tourist account."
    return None


def login_tourist(email: str, password: str) -> tuple[bool, str | None]:
    email = email.strip().lower()
    try:
        response = get_supabase().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthApiError as exc:
        return False, _friendly_auth_error(exc)
    except Exception:
        return False, "Unable to sign in right now. Please try again later."

    user = response.user
    if not user:
        return False, "Sign in failed. Please check your credentials."

    if not _is_tourist(user):
        try:
            get_supabase().auth.sign_out()
        except Exception:
            pass
        return (
            False,
            "This account is not a tourist profile. Tourist accounts must be created "
            "through the sign-up page below.",
        )

    _set_session(user, response.session)
    return True, None


def register_tourist(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    middle_name: str = "",
) -> tuple[bool, str | None, bool]:
    """
    Returns (success, error_message, email_confirmation_required).
    """
    first_name = first_name.strip()
    last_name = last_name.strip()
    middle_name = (middle_name or "").strip()
    email = email.strip().lower()

    try:
        response = get_supabase().auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "first_name": first_name,
                        "middle_name": middle_name or None,
                        "last_name": last_name,
                        "role": TOURIST_ROLE,
                    }
                },
            }
        )
    except AuthApiError as exc:
        return False, _friendly_auth_error(exc), False
    except Exception:
        return False, "Unable to create your account right now. Please try again later.", False

    user = response.user
    if not user:
        return False, "Registration failed. Please try again.", False

    try:
        # Attempt to insert into profiles table
        role_res = get_supabase().table("roles").select("id").eq("role_key", TOURIST_ROLE).execute()
        if role_res.data:
            role_id = role_res.data[0]["id"]
            
            get_supabase().table("profiles").insert({
                "id": user.id,
                "first_name": first_name,
                "middle_name": middle_name or None,
                "last_name": last_name,
                "email": email,
                "role_id": role_id
            }).execute()
    except Exception as e:
        print(f"Warning: Could not create profile manually (possibly handled by DB trigger): {e}")

    email_confirmation_required = not bool(response.session)
    if response.session:
        _set_session(user, response.session)

    return True, None, email_confirmation_required


def _friendly_auth_error(exc: AuthApiError) -> str:
    message = str(exc).lower()
    if "invalid login credentials" in message or "invalid credentials" in message:
        return "Incorrect email or password."
    if "already registered" in message or "already been registered" in message:
        return "An account with this email already exists. Try signing in instead."
    if "password" in message and "weak" in message:
        return "Choose a stronger password (at least 8 characters)."
    if "email" in message and "invalid" in message:
        return "Enter a valid email address."
    return "Authentication failed. Please check your details and try again."
