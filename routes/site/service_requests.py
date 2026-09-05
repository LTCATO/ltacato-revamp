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
                    "requester_name": request.form.get("requester_name")
                    or (tourist or {}).get("name"),
                    "requester_email": requester_email or (tourist or {}).get("email"),
                    "requester_phone": request.form.get("requester_phone"),
                    "message": request.form.get("message"),
                    "tourist_id": tourist["id"] if tourist else None,
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
            "Request submitted — LTCATO will follow up by email.",
            "success",
        )
        if tourist:
            return redirect(url_for("service_requests.my_requests"))
        # An anonymous submitter has no "My requests" page to land on — send
        # them to a distinct confirmation state instead of back to the same
        # blank form, where a genuine success looked identical to a silent
        # failure.
        return redirect(url_for("service_requests.new_request", sent="1"))

    return render_template(
        "views/site/service_requests/new.html",
        catalog=catalog,
        tourist=tourist,
        sent=request.args.get("sent") == "1",
    )


@service_requests_bp.route("/my-requests")
@tourist_login_required
def my_requests():
    tourist = get_current_tourist()
    requests_ = get_user_service_requests(tourist["id"])
    return render_template(
        "views/site/service_requests/my_requests.html", requests=requests_
    )
