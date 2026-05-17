from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.itineraries import list_user_itineraries
from services.profiles import get_tourist_profile, profile_display_name, update_tourist_profile
from services.tourist_auth import get_current_tourist
from services.tourist_passport import get_or_create_passport, list_passport_stamps, stamp_spot
from utils.jinja_helpers import normalize_image_url
from utils.tourist_helpers import tourist_login_required

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile", methods=["GET", "POST"])
@tourist_login_required
def tourist_profile():
    tourist = get_current_tourist()
    assert tourist

    profile = get_tourist_profile(tourist["id"])
    if not profile:
        flash("Profile not found. Please contact support.", "danger")
        return redirect(url_for("public.home"))

    passport = get_or_create_passport(tourist["id"])
    stamps: list = []
    if passport:
        stamps = list_passport_stamps(passport["id"])

    trips = list_user_itineraries(tourist["id"], limit=6)

    form_data = {
        "first_name": profile.get("first_name") or "",
        "middle_name": profile.get("middle_name") or "",
        "last_name": profile.get("last_name") or "",
        "email": profile.get("email") or tourist.get("email") or "",
        "profile_image": profile.get("profile_image") or "",
    }

    if request.method == "POST":
        action = (request.form.get("action") or "profile").strip()

        if action == "stamp":
            spot_id = request.form.get("spot_id", type=int)
            if passport and spot_id:
                if stamp_spot(passport["id"], spot_id):
                    flash("Passport stamp collected!", "success")
                else:
                    flash("Could not add stamp.", "danger")
            return redirect(url_for("profile.tourist_profile"))

        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        middle_name = (request.form.get("middle_name") or "").strip()
        profile_image = (request.form.get("profile_image") or "").strip() or None

        ok, err = update_tourist_profile(
            tourist["id"],
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            profile_image=profile_image,
        )
        if ok:
            session["tourist_name"] = f"{first_name} {last_name}".strip() or session.get(
                "tourist_name", "Traveler"
            )
            flash("Profile updated successfully.", "success")
            return redirect(url_for("profile.tourist_profile"))
        flash(err or "Update failed.", "danger")
        form_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "last_name": last_name,
            "email": form_data["email"],
            "profile_image": profile_image or "",
        }

    avatar = normalize_image_url(form_data.get("profile_image"))

    return render_template(
        "views/site/profile/edit.html",
        profile=profile,
        display_name=profile_display_name(profile),
        form_data=form_data,
        avatar=avatar,
        passport=passport,
        stamps=stamps,
        trips=trips,
    )
