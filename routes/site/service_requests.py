import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services.email_service import send_service_request_email
from services.service_requests import (
    create_service_request,
    get_service_catalog,
    get_user_service_requests,
)
from services.tourist_auth import EMAIL_PATTERN, get_current_tourist
from utils.tourist_helpers import tourist_login_required

logger = logging.getLogger(__name__)

service_requests_bp = Blueprint("service_requests", __name__)


@service_requests_bp.route("/request-service", methods=["GET", "POST"])
def new_request():
    tourist = get_current_tourist()
    catalog = get_service_catalog()

    if request.method == "POST":
        if not tourist:
            # The page itself is public so anyone can see what's required
            # before committing — same as spots/events, only actually
            # submitting a review/request needs an account. A direct POST
            # while logged out (bypassing the UI, which only shows a Sign in
            # link in that state) is redirected the same way.
            flash("Please sign in to submit a request.", "warning")
            return redirect(url_for("auth.login", next=url_for("service_requests.new_request")))

        requester_email = (request.form.get("requester_email") or "").strip().lower()
        if requester_email and not EMAIL_PATTERN.match(requester_email):
            flash("Enter a valid email address.", "danger")
            return render_template(
                "views/site/service_requests/new.html", catalog=catalog, tourist=tourist
            )
        try:
            created = create_service_request(
                {
                    "service_number": request.form.get("service_number"),
                    "requester_name": request.form.get("requester_name") or tourist.get("name"),
                    "requester_email": requester_email or tourist.get("email"),
                    "requester_phone": request.form.get("requester_phone"),
                    "message": request.form.get("message"),
                    "tourist_id": tourist["id"],
                }
            )
            send_service_request_email(created)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "views/site/service_requests/new.html", catalog=catalog, tourist=tourist
            )
        except Exception:
            logger.exception("service request submission failed")
            flash("Couldn't submit your request right now. Please try again.", "danger")
            return render_template(
                "views/site/service_requests/new.html", catalog=catalog, tourist=tourist
            )

        flash(
            "Request submitted — LTCATO will follow up by email and you can track "
            "its status under My requests.",
            "success",
        )
        return redirect(url_for("service_requests.my_requests"))

    return render_template(
        "views/site/service_requests/new.html",
        catalog=catalog,
        tourist=tourist,
    )


@service_requests_bp.route("/my-requests")
@tourist_login_required
def my_requests():
    tourist = get_current_tourist()
    requests_ = get_user_service_requests(tourist["id"])
    return render_template(
        "views/site/service_requests/my_requests.html", requests=requests_
    )
