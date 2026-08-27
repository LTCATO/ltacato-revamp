# pyrefly: ignore [missing-import]
import secrets

from flask import flash, jsonify, redirect, request, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required, role_required
from services.dashboard_auth import (
    assign_profile_lgu_id,
    get_current_dashboard_user,
    resolve_dashboard_lgu_id,
)
from services.supabase_client import get_supabase


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/approve", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def approve_chatbot(entry_id: int):
    from services.chatbot_context import invalidate as invalidate_chat_cache

    user = get_current_dashboard_user()
    get_supabase().table("chatbot_knowledge").update(
        {"approval_status": "approved", "approved_by": str(user["id"])}
    ).eq("id", entry_id).execute()
    invalidate_chat_cache("faq")
    flash("FAQ entry approved for the chatbot.", "success")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def reject_chatbot(entry_id: int):
    from services.chatbot_context import invalidate as invalidate_chat_cache

    get_supabase().table("chatbot_knowledge").update(
        {"approval_status": "rejected"}
    ).eq("id", entry_id).execute()
    invalidate_chat_cache("faq")
    flash("FAQ entry rejected.", "info")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/add", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def add_chatbot_entry():
    from services.chatbot_knowledge import create_knowledge

    user = get_current_dashboard_user()
    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()
    category = request.form.get("category", "").strip()

    # Both super_admin and ltcato_staff auto-approve — they have equivalent trust
    ok, err = create_knowledge(
        question=question,
        answer=answer,
        category=category,
        created_by=str(user["id"]),
        auto_approve=True,
    )
    if ok:
        from services.chatbot_context import invalidate as invalidate_chat_cache

        invalidate_chat_cache("faq")
        flash("FAQ entry added and is now active in LARA's knowledge base.", "success")
    else:
        flash(err or "Could not add FAQ entry.", "danger")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/edit", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def edit_chatbot_entry(entry_id: int):
    from services.chatbot_knowledge import update_knowledge

    user = get_current_dashboard_user()
    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()
    category = request.form.get("category", "").strip()

    # Both roles are trusted — keep entry approved after edit
    ok, err = update_knowledge(
        entry_id,
        question=question,
        answer=answer,
        category=category,
        approved_by=str(user["id"]),
    )
    if ok:
        from services.chatbot_context import invalidate as invalidate_chat_cache

        invalidate_chat_cache("faq")
        flash("FAQ entry updated.", "success")
    else:
        flash(err or "Could not update FAQ entry.", "danger")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/delete", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def delete_chatbot_entry(entry_id: int):
    from services.chatbot_knowledge import delete_knowledge

    ok, err = delete_knowledge(entry_id)
    if ok:
        flash("FAQ entry deleted.", "info")
    else:
        flash(err or "Could not delete FAQ entry.", "danger")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/unanswered/<int:entry_id>/promote", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def promote_unanswered_query(entry_id: int):
    from services.chatbot_unanswered import promote_to_knowledge

    user = get_current_dashboard_user()
    answer = request.form.get("answer", "").strip()
    category = request.form.get("category", "").strip()

    ok, err = promote_to_knowledge(
        entry_id, answer=answer, category=category, created_by=str(user["id"])
    )
    if ok:
        from services.chatbot_context import invalidate as invalidate_chat_cache

        invalidate_chat_cache("faq")
        flash("Logged question promoted to FAQ and is now active in LARA's knowledge base.", "success")
    else:
        flash(err or "Could not promote logged question.", "danger")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/unanswered/<int:entry_id>/dismiss", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def dismiss_unanswered_query(entry_id: int):
    from services.chatbot_unanswered import dismiss_unanswered_query as _dismiss

    ok, err = _dismiss(entry_id)
    if ok:
        flash("Logged question dismissed.", "info")
    else:
        flash(err or "Could not dismiss logged question.", "danger")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/spot/<int:spot_id>/approve-ltcato", methods=["POST"])
@dashboard_login_required
@role_required("ltcato_staff")
def approve_spot_ltcato(spot_id: int):
    from services.chatbot_context import invalidate as invalidate_chat_cache

    get_supabase().table("tourist_spots").update({"approval_status": "approved"}).eq(
        "id", spot_id
    ).execute()
    invalidate_chat_cache("spots")
    flash("Tourist spot approved for the public directory.", "success")
    return redirect(url_for("dashboard.lgu_management"))


@dashboard_bp.route("/actions/spot/<int:spot_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("ltcato_staff")
def reject_spot(spot_id: int):
    from services.chatbot_context import invalidate as invalidate_chat_cache

    get_supabase().table("tourist_spots").update({"approval_status": "rejected"}).eq(
        "id", spot_id
    ).execute()
    invalidate_chat_cache("spots")
    flash("Tourist spot rejected.", "info")
    return redirect(url_for("dashboard.lgu_management"))


@dashboard_bp.route("/actions/form/save", methods=["POST"])
@dashboard_login_required
def form_save_stub():
    form_type = request.form.get("form_type", "record")
    if form_type == "arrival_report":
        return _save_arrival_report()
    if form_type == "site_update":
        return _save_site_update()
    flash(f"{form_type.replace('_', ' ').title()} saved successfully.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))


@dashboard_bp.route("/actions/arrival-record/<int:record_id>/delete", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def delete_arrival_record(record_id: int):
    """Delete a draft arrival record (establishment owner only)."""
    from services.arrival_reports import delete_arrival_report

    user = get_current_dashboard_user()
    try:
        delete_arrival_report(record_id, owner_id=str(user.get("id")))
        flash("Draft record deleted.", "info")
    except PermissionError:
        flash("You can only delete your own records.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not delete record: {exc}", "danger")
    return redirect(url_for("dashboard.arrivals"))


@dashboard_bp.route("/actions/visit-schedule/<int:visit_id>/<new_status>", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def update_visit_status(visit_id: int, new_status: str):
    """Confirm/decline/complete/cancel a visit request (establishment owner only)."""
    from services.visit_schedules import update_visit_status as _update_visit_status

    user = get_current_dashboard_user()
    try:
        _update_visit_status(visit_id, new_status, owner_id=str(user.get("id")))
        flash(f"Visit request marked as {new_status}.", "success")
    except PermissionError:
        flash("You can only manage visits for your own establishment.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not update visit: {exc}", "danger")
    return redirect(url_for("dashboard.visit_schedules"))


@dashboard_bp.route("/actions/visit-schedule/<int:visit_id>/check-in", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def check_in_visit(visit_id: int):
    """One-click 'Mark arrived' — stamps arrived_at and completes the visit."""
    from services.visit_schedules import check_in_visit as _check_in_visit

    user = get_current_dashboard_user()
    try:
        _check_in_visit(visit_id, owner_id=str(user.get("id")))
        flash("Visit marked as arrived.", "success")
    except PermissionError:
        flash("You can only manage visits for your own establishment.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not check in visit: {exc}", "danger")
    return redirect(url_for("dashboard.visit_schedules"))


@dashboard_bp.route("/actions/visit-schedule/<int:visit_id>/undo-check-in", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def undo_check_in(visit_id: int):
    """Revert an accidental 'Mark arrived' click back to confirmed."""
    from services.visit_schedules import undo_check_in as _undo_check_in

    user = get_current_dashboard_user()
    try:
        _undo_check_in(visit_id, owner_id=str(user.get("id")))
        flash("Check-in undone.", "info")
    except PermissionError:
        flash("You can only manage visits for your own establishment.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not undo check-in: {exc}", "danger")
    return redirect(url_for("dashboard.visit_schedules"))


@dashboard_bp.route("/actions/visit-schedule/manual-log", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def add_manual_log():
    """Record a walk-in visitor who didn't schedule online."""
    from services.visit_schedules import create_manual_log

    user = get_current_dashboard_user()
    try:
        create_manual_log(
            {
                "tourist_spot_id": request.form.get("tourist_spot_id", type=int),
                "visitor_name": request.form.get("visitor_name", ""),
                "visitor_email": (request.form.get("visitor_email") or "").strip() or None,
                "visitor_phone": (request.form.get("visitor_phone") or "").strip() or None,
                "party_size": request.form.get("party_size", type=int) or 1,
                "visit_date": request.form.get("visit_date"),
                "visit_time": request.form.get("visit_time") or "00:00",
                "visitor_category": request.form.get("visitor_category") or "day_tour",
                "overnight_nights": request.form.get("overnight_nights", type=int) or 0,
                "origin": request.form.get("origin") or None,
                "male_count": request.form.get("male_count", type=int),
                "female_count": request.form.get("female_count", type=int),
                "notes": (request.form.get("notes") or "").strip() or None,
            },
            owner_id=str(user.get("id")),
        )
        flash("Manual log added.", "success")
    except PermissionError:
        flash("You can only log visits for your own establishment.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not add manual log: {exc}", "danger")
    return redirect(url_for("dashboard.visit_schedules", tab="logs"))


@dashboard_bp.route("/actions/visit-schedule/<int:visit_id>/demographics", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def update_visit_demographics(visit_id: int):
    """Backfill/edit the origin + male/female breakdown for a log row."""
    from services.visit_schedules import update_visit_demographics as _update_demographics

    user = get_current_dashboard_user()
    try:
        _update_demographics(
            visit_id,
            owner_id=str(user.get("id")),
            visitor_category=request.form.get("visitor_category"),
            overnight_nights=request.form.get("overnight_nights", type=int),
            origin=request.form.get("origin") or None,
            male_count=request.form.get("male_count", type=int),
            female_count=request.form.get("female_count", type=int),
        )
        flash("Log updated.", "success")
    except PermissionError:
        flash("You can only manage visits for your own establishment.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not update log: {exc}", "danger")
    return redirect(url_for("dashboard.visit_schedules", tab="logs"))


@dashboard_bp.route("/actions/arrival-report/generate", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def generate_arrival_report():
    """Generate and submit an LTCATO arrival report aggregated from real visit logs."""
    from services.visit_schedules import generate_and_submit_arrival_report

    user = get_current_dashboard_user()
    report_type = request.form.get("report_type") or "daily"
    visitor_category = request.form.get("visitor_category") or "day_tour"
    date_from = request.form.get("date_from") or ""
    date_to = request.form.get("date_to") or date_from
    if report_type == "daily":
        date_to = date_from

    try:
        _report, unclassified_count = generate_and_submit_arrival_report(
            owner_id=str(user.get("id")),
            spot_id=request.form.get("tourist_spot_id", type=int),
            visitor_category=visitor_category,
            report_type=report_type,
            date_from=date_from,
            date_to=date_to,
        )
        flash("Arrival report generated and submitted to your LGU.", "success")
        if unclassified_count:
            flash(
                f"{unclassified_count} visitor(s) in this range have no residence recorded "
                "and are excluded from the LTCATO breakdown — still counted in your Logs. "
                "Edit their demographics on the Logs page to include them.",
                "warning",
            )
    except PermissionError:
        flash("You can only generate reports for your own establishment.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not generate report: {exc}", "danger")
    return redirect(url_for("dashboard.arrivals"))


@dashboard_bp.route("/actions/arrival-records/compile", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def compile_arrival_records():
    """
    Compile (submit) all draft records for a given spot + category + date
    to the LGU Tourism Office. The report_type (daily/weekly) is chosen here
    and applied to all matching drafts.
    """
    from services.arrival_reports import submit_draft_records
    from services.spots import list_spots_for_dashboard

    user = get_current_dashboard_user()
    owner_id = str(user.get("id"))

    spot_id_raw = request.form.get("tourist_spot_id", "").strip()
    visitor_category = request.form.get("visitor_category", "").strip()
    report_type = request.form.get("report_type", "").strip()
    compile_date = request.form.get("compile_date", "").strip()

    if not spot_id_raw.isdigit():
        flash("Invalid tourist spot.", "danger")
        return redirect(url_for("dashboard.arrivals"))
    if visitor_category not in ("day_tour", "overnight"):
        flash("Invalid visitor category.", "danger")
        return redirect(url_for("dashboard.arrivals"))
    if report_type not in ("daily", "weekly"):
        flash("Invalid report type.", "danger")
        return redirect(url_for("dashboard.arrivals"))
    if not compile_date:
        flash("Select a date to compile.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    spot_id = int(spot_id_raw)
    owned = list_spots_for_dashboard(owner_id=owner_id, limit=20)
    owned_ids = {int(s["id"]) for s in owned if s.get("id") is not None}
    if spot_id not in owned_ids:
        flash("You can only compile records for your own establishment.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    try:
        count = submit_draft_records(
            owner_id=owner_id,
            spot_id=spot_id,
            visitor_category=visitor_category,
            report_type=report_type,
            compile_date=compile_date,
        )
        if count:
            category_label = "day tour" if visitor_category == "day_tour" else "overnight"
            flash(
                f"{count} {category_label} draft(s) for {compile_date} compiled as "
                f"'{report_type}' and submitted to your LGU Tourism Office.",
                "success",
            )
        else:
            flash(
                f"No draft records found for {compile_date} matching the selected filters.",
                "warning",
            )
    except Exception as exc:
        flash(f"Could not compile records: {exc}", "danger")
    return redirect(url_for("dashboard.arrivals"))

@dashboard_bp.route("/actions/event/save", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff", "lgu_admin")
def save_event():
    from services.events import create_event_from_request

    user = get_current_dashboard_user()
    forced_lgu_id = resolve_dashboard_lgu_id(user) if user["role"] == "lgu_admin" else None
    approval_status = "pending" if user["role"] == "lgu_admin" else "approved"
    try:
        event = create_event_from_request(
            request.form,
            request.files,
            created_by=str(user.get("id") or ""),
            forced_lgu_id=forced_lgu_id,
            approval_status=approval_status,
        )
        if approval_status == "pending":
            flash("Event submitted and is pending LTCATO approval.", "success")
        else:
            flash("Event published successfully.", "success")
        if event.get("_exhibitor_save_failed"):
            flash(
                "The event saved, but the exhibitor list could not be saved. "
                "Please re-add exhibitors for this event.",
                "warning",
            )
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(
            f"Could not save event: {exc}. "
            "If you just added new columns, run the Supabase migration. "
            "For uploads, ensure Storage bucket exists (see SUPABASE_STORAGE_BUCKET).",
            "danger",
        )
    return redirect(url_for("dashboard.promotions"))


def _can_manage_event(user, event: dict) -> bool:
    if user["role"] in ("super_admin", "ltcato_staff"):
        return True
    if user["role"] == "lgu_admin":
        return int(event.get("lgu_id") or -1) == int(resolve_dashboard_lgu_id(user) or -2)
    return False


@dashboard_bp.route("/actions/event/<int:event_id>/edit-data")
@dashboard_login_required
@role_required("super_admin", "ltcato_staff", "lgu_admin")
def event_edit_data(event_id: int):
    """JSON snapshot of an event for the dashboard edit modal to populate."""
    from services.events import get_event

    user = get_current_dashboard_user()
    event = get_event(event_id, public_only=False)
    if not event:
        return jsonify({"error": "Event not found."}), 404
    if not _can_manage_event(user, event):
        return jsonify({"error": "You can only edit your own LGU's events."}), 403
    return jsonify(event)


@dashboard_bp.route("/actions/event/<int:event_id>/update", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff", "lgu_admin")
def update_event(event_id: int):
    from services.events import get_event, update_event_from_request

    user = get_current_dashboard_user()
    existing = get_event(event_id, public_only=False)
    if not existing:
        flash("Event not found.", "danger")
        return redirect(url_for("dashboard.promotions"))
    if not _can_manage_event(user, existing):
        flash("You can only edit your own LGU's events.", "danger")
        return redirect(url_for("dashboard.promotions"))

    is_lgu_admin = user["role"] == "lgu_admin"
    forced_lgu_id = resolve_dashboard_lgu_id(user) if is_lgu_admin else None
    # An LGU-submitted edit needs re-review like a new submission; an
    # LTCATO/super_admin edit keeps whatever approval state the event
    # already had (fixing a typo shouldn't silently re-approve a rejected
    # event or require re-approving an already-approved one).
    approval_status = "pending" if is_lgu_admin else (existing.get("approval_status") or "approved")
    try:
        event = update_event_from_request(
            event_id,
            request.form,
            request.files,
            forced_lgu_id=forced_lgu_id,
            approval_status=approval_status,
        )
        if is_lgu_admin:
            flash("Event updated and re-submitted for LTCATO approval.", "success")
        else:
            flash("Event updated successfully.", "success")
        if event.get("_exhibitor_save_failed"):
            flash(
                "The event saved, but the exhibitor list could not be updated. "
                "Please re-add exhibitors for this event.",
                "warning",
            )
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(
            f"Could not update event: {exc}. "
            "If you just added new columns, run the Supabase migration. "
            "For uploads, ensure Storage bucket exists (see SUPABASE_STORAGE_BUCKET).",
            "danger",
        )
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/event/<int:event_id>/approve", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def approve_event(event_id: int):
    from services.chatbot_context import invalidate as invalidate_chat_cache

    get_supabase().table("events").update({"approval_status": "approved"}).eq(
        "id", event_id
    ).execute()
    invalidate_chat_cache("events")
    flash("Event approved and published.", "success")
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/event/<int:event_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def reject_event(event_id: int):
    from services.chatbot_context import invalidate as invalidate_chat_cache

    get_supabase().table("events").update({"approval_status": "rejected"}).eq(
        "id", event_id
    ).execute()
    invalidate_chat_cache("events")
    flash("Event rejected.", "info")
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/event/<int:event_id>/request-featured", methods=["POST"])
@dashboard_login_required
@role_required("lgu_admin")
def request_event_featured(event_id: int):
    from services.events import request_event_featured as _request_featured

    user = get_current_dashboard_user()
    lgu_id = resolve_dashboard_lgu_id(user)
    try:
        _request_featured(
            event_id,
            requested_by=str(user.get("id")),
            lgu_id=lgu_id,
        )
        flash("Featured request submitted for LTCATO review.", "success")
    except PermissionError:
        flash("You can only request Featured for your own LGU's events.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/event/<int:event_id>/featured/<decision>", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def review_event_featured(event_id: int, decision: str):
    from services.events import review_event_featured as _review_featured

    user = get_current_dashboard_user()
    if decision not in ("approve", "reject"):
        flash("Invalid decision.", "danger")
        return redirect(url_for("dashboard.promotions"))
    try:
        _review_featured(event_id, approve=(decision == "approve"), reviewed_by=str(user.get("id")))
        from services.chatbot_context import invalidate as invalidate_chat_cache

        invalidate_chat_cache("events")
        flash(f"Featured request {decision}d.", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/event/<int:event_id>/notify-visitors", methods=["POST"])
@dashboard_login_required
@role_required("lgu_admin", "ltcato_staff", "super_admin")
def notify_event_visitors(event_id: int):
    """Email tourists who've completed a visit to a spot in this event's LGU."""
    from services.email_service import send_email
    from services.visit_schedules import list_previous_visitor_emails_for_lgu

    user = get_current_dashboard_user()
    event_res = (
        get_supabase().table("events").select("id, title, lgu_id").eq("id", event_id).execute()
    )
    rows = event_res.data or []
    if not rows:
        flash("Event not found.", "danger")
        return redirect(url_for("dashboard.promotions"))
    event = rows[0]
    lgu_id = event.get("lgu_id")
    if not lgu_id:
        flash("This event isn't tied to a specific LGU, so there's no visitor list to notify.", "warning")
        return redirect(url_for("dashboard.promotions"))
    if user["role"] == "lgu_admin" and int(lgu_id) != int(resolve_dashboard_lgu_id(user) or -1):
        flash("You can only notify visitors for events in your own LGU.", "danger")
        return redirect(url_for("dashboard.promotions"))

    emails = list_previous_visitor_emails_for_lgu(lgu_id, limit=300)
    subject = f"New event: {event['title']}"
    body = (
        f"<p>A new event, <strong>{event['title']}</strong>, has just been posted "
        "for a destination you've previously visited. Check it out on the LTCATO site!</p>"
    )
    sent = sum(1 for email in emails if send_email(email, subject, body))
    flash(f"Notified {sent} of {len(emails)} previous visitor(s).", "success")
    return redirect(url_for("dashboard.promotions"))


def _save_arrival_report():
    from services.arrival_reports import create_arrival_report
    from services.spots import list_spots_for_dashboard

    user = get_current_dashboard_user()
    role = user["role"]

    # Only establishment owners save draft records via this form
    if role != "establishment_owner":
        flash("Your role cannot save arrival records this way.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    visitor_category = request.form.get("visitor_category", "day_tour")
    if visitor_category not in ("day_tour", "overnight"):
        flash("Invalid visitor category.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    # Date is always today — this acts as a logbook, no manual date entry
    from datetime import date as _date
    report_date = _date.today().isoformat()

    # report_type is not chosen at save time — default to "daily"
    # The actual type (daily/weekly) is chosen at compile time
    report_type = "daily"

    lgu_id = resolve_dashboard_lgu_id(user)
    spot_id_raw = request.form.get("tourist_spot_id")
    tourist_spot_id = int(spot_id_raw) if spot_id_raw else None

    owned = list_spots_for_dashboard(owner_id=user.get("id"), limit=20)
    owned_ids = {int(s["id"]) for s in owned if s.get("id") is not None}
    if not tourist_spot_id or tourist_spot_id not in owned_ids:
        flash("Select a valid establishment for this record.", "danger")
        return redirect(url_for("dashboard.arrivals"))
    spot = next((s for s in owned if int(s["id"]) == tourist_spot_id), None)
    lgu_id = spot.get("lgu_id") if spot else lgu_id

    count_fields = (
        "this_city_male", "this_city_female",
        "other_city_male", "other_city_female",
        "other_province_male", "other_province_female",
        "foreign_male", "foreign_female",
    )
    payload: dict = {
        "tourist_spot_id": tourist_spot_id,
        "lgu_id": int(lgu_id) if lgu_id else None,
        "submitted_by": user.get("id"),
        "report_type": report_type,
        "report_date": report_date,
        "visitor_category": visitor_category,
        "overnight_nights": int(request.form.get("overnight_nights") or 0),
        "status": "draft",
    }
    for field in count_fields:
        payload[field] = int(request.form.get(field) or 0)

    if visitor_category == "overnight" and payload["overnight_nights"] <= 0:
        flash("Enter the number of guest-nights for overnight arrivals.", "danger")
        return redirect(url_for("dashboard.arrivals"))
    if visitor_category == "day_tour":
        from services.arrival_reports import report_total_visitors
        if report_total_visitors(payload) <= 0:
            flash("Enter at least one day-tour visitor count.", "danger")
            return redirect(url_for("dashboard.arrivals"))

    try:
        create_arrival_report(payload)
        label = "Overnight" if visitor_category == "overnight" else "Day tour"
        flash(
            f"{label} record saved as draft for {report_date}. "
            "Review your drafts and use Compile & Submit when ready to send to your LGU.",
            "success",
        )
    except Exception as exc:
        flash(f"Could not save record: {exc}", "danger")
    return redirect(url_for("dashboard.arrivals"))


def _generate_temp_password() -> str:
    """A one-off temporary password for a newly created account.

    Each account gets its own random value instead of a shared constant, so
    knowing one account's temp password doesn't hand out access to every
    other account created the same way.
    """
    return secrets.token_urlsafe(9)


@dashboard_bp.route("/actions/accounts/staff", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def create_staff_account():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    position = request.form.get("position", "").strip()
    temp_password = _generate_temp_password()

    try:
        response = get_supabase().auth.admin.create_user(
            {
                "email": email,
                "password": temp_password,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "ltcato_staff",
                },
            }
        )
        user = response.user

        # Insert into profiles
        role_res = (
            get_supabase()
            .table("roles")
            .select("id")
            .eq("role_key", "ltcato_staff")
            .execute()
        )
        if role_res.data:
            role_id = role_res.data[0]["id"]
            get_supabase().table("profiles").upsert(
                {
                    "id": user.id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "role_id": role_id,
                    "position": position,
                }
            ).execute()

        flash(
            f"LTCATO staff account created for {email} with temporary password {temp_password} "
            "— share it securely and ask them to change it after signing in.",
            "success",
        )
    except Exception as e:
        flash(f"Failed to create account: {str(e)}", "danger")

    return redirect(url_for("dashboard.accounts"))


@dashboard_bp.route("/actions/accounts/lgu", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def create_lgu_account():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    position = request.form.get("position", "").strip()
    lgu_id = request.form.get("lgu_id")
    temp_password = _generate_temp_password()

    try:
        response = get_supabase().auth.admin.create_user(
            {
                "email": email,
                "password": temp_password,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "lgu_admin",
                    "lgu_id": int(lgu_id) if lgu_id else None,
                },
            }
        )
        user = response.user

        # Insert into profiles
        role_res = (
            get_supabase()
            .table("roles")
            .select("id")
            .eq("role_key", "lgu_admin")
            .execute()
        )
        if role_res.data:
            role_id = role_res.data[0]["id"]
            get_supabase().table("profiles").upsert(
                {
                    "id": user.id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "role_id": role_id,
                    "lgu_id": int(lgu_id) if lgu_id else None,
                    "position": position,
                }
            ).execute()

        flash(
            f"LGU account created for {email} with temporary password {temp_password} "
            "— share it securely and ask them to change it after signing in.",
            "success",
        )
    except Exception as e:
        flash(f"Failed to create LGU account: {str(e)}", "danger")

    return redirect(url_for("dashboard.accounts"))


@dashboard_bp.route("/actions/accounts/owner", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff", "lgu_admin")
def create_owner_account():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    position = request.form.get("position", "").strip()
    temp_password = _generate_temp_password()

    user = get_current_dashboard_user()
    if user["role"] == "lgu_admin":
        lgu_id = resolve_dashboard_lgu_id(user)
    else:
        lgu_raw = request.form.get("lgu_id", "").strip()
        lgu_id = int(lgu_raw) if lgu_raw.isdigit() else None

    if user["role"] == "lgu_admin" and not lgu_id:
        flash(
            "Your LGU profile is not set. Ask LTCATO staff to link your account to a municipality.",
            "danger",
        )
        return redirect(url_for("dashboard.tourist_spots"))

    lgu_id_int = int(lgu_id) if lgu_id is not None else None

    try:
        response = get_supabase().auth.admin.create_user(
            {
                "email": email,
                "password": "ltcato@2026",
                "email_confirm": True,
                "user_metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "establishment_owner",
                    "lgu_id": lgu_id_int,
                },
            }
        )
        new_user = response.user

        # Upsert into profiles
        role_res = (
            get_supabase()
            .table("roles")
            .select("id")
            .eq("role_key", "establishment_owner")
            .execute()
        )
        if role_res.data:
            role_id = role_res.data[0]["id"]
            get_supabase().table("profiles").upsert(
                {
                    "id": new_user.id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "role_id": role_id,
                    "lgu_id": lgu_id_int,
                    "position": position,
                }
            ).execute()

        flash(
            f"Establishment owner account created for {email} with temporary password {temp_password} "
            "— share it securely and ask them to change it after signing in.",
            "success",
        )
    except Exception as e:
        flash(f"Failed to create owner account: {str(e)}", "danger")

    fallback = (
        url_for("dashboard.tourist_spots")
        if user["role"] == "lgu_admin"
        else url_for("dashboard.accounts")
    )
    return redirect(request.referrer or fallback)


@dashboard_bp.route("/actions/spot/register", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def register_establishment_spot():
    from services.spots import create_tourist_spot_for_owner

    user = get_current_dashboard_user()
    owner_id = str(user.get("id") or "")

    lgu_id = resolve_dashboard_lgu_id(user)
    if not lgu_id:
        flash(
            "Your account is not linked to an LGU. Contact your LGU tourism office.",
            "danger",
        )
        return redirect(url_for("dashboard.site_updates"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Establishment name is required.", "danger")
        return redirect(url_for("dashboard.site_updates"))

    category_raw = request.form.get("category_id", "").strip()
    code_raw = request.form.get("code", "").strip()
    if not category_raw.isdigit() or not code_raw.isdigit():
        flash("Select a category and attraction code.", "danger")
        return redirect(url_for("dashboard.site_updates"))
    category_id = int(category_raw)
    code = int(code_raw)

    from services.spots import code_belongs_to_category

    if not code_belongs_to_category(category_id=category_id, code=code):
        flash("Invalid attraction code for the selected category.", "danger")
        return redirect(url_for("dashboard.site_updates"))

    try:
        create_tourist_spot_for_owner(
            owner_id=owner_id,
            lgu_id=int(lgu_id),
            name=name,
            description=request.form.get("description"),
            address=request.form.get("address"),
            opening_hours=request.form.get("opening_hours"),
            category_id=category_id,
            code=code,
            main_image=request.files.get("main_image"),
            gallery_files=request.files.getlist("gallery_images"),
        )
        flash(
            "Establishment submitted for LGU approval. You can update details once approved.",
            "success",
        )
    except Exception as exc:
        flash(f"Could not register establishment: {exc}", "danger")
    return redirect(url_for("dashboard.site_updates"))


@dashboard_bp.route("/actions/spot/claim", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def claim_establishment_spot():
    from services.spots import claim_tourist_spot_for_owner

    user = get_current_dashboard_user()
    owner_id = str(user.get("id") or "")

    lgu_id = resolve_dashboard_lgu_id(user)
    if not lgu_id:
        flash("Your account is not linked to an LGU.", "danger")
        return redirect(url_for("dashboard.site_updates"))

    spot_id_raw = request.form.get("spot_id", "").strip()
    if not spot_id_raw.isdigit():
        flash("Invalid establishment.", "danger")
        return redirect(url_for("dashboard.site_updates"))

    try:
        claim_tourist_spot_for_owner(
            spot_id=int(spot_id_raw),
            owner_id=owner_id,
            lgu_id=int(lgu_id),
        )
        flash(
            "Establishment linked to your account. You can update listing details below.",
            "success",
        )
    except Exception as exc:
        flash(f"Could not claim establishment: {exc}", "danger")
    return redirect(url_for("dashboard.site_updates"))


def _save_site_update():
    from services.spots import list_spots_for_dashboard, update_tourist_spot_for_owner

    user = get_current_dashboard_user()
    owner_id = str(user.get("id") or "")
    spot_id_raw = request.form.get("spot_id", "").strip()
    if not spot_id_raw.isdigit():
        flash("Invalid establishment.", "danger")
        return redirect(url_for("dashboard.site_updates"))

    spot_id = int(spot_id_raw)
    owned = list_spots_for_dashboard(owner_id=owner_id, limit=10)
    owned_ids = {int(s["id"]) for s in owned if s.get("id") is not None}
    if spot_id not in owned_ids:
        flash("You can only update your own establishment.", "danger")
        return redirect(url_for("dashboard.site_updates"))

    fields = {
        k: request.form.get(k, "").strip()
        for k in (
            "description",
            "opening_hours",
            "best_time_to_visit",
            "hook_title",
            "hook_text",
            "entrance_fees",
            "what_to_bring",
        )
    }
    try:
        update_tourist_spot_for_owner(spot_id, owner_id=owner_id, fields=fields)
        flash("Establishment listing updated.", "success")
    except Exception as exc:
        flash(f"Could not save updates: {exc}", "danger")
    return redirect(url_for("dashboard.site_updates"))


# ---------------------------------------------------------------------------
# Decision Support — scraper trigger routes
# ---------------------------------------------------------------------------


@dashboard_bp.route("/actions/scrape/reviews", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def scrape_reviews():
    """Scrape online reviews from Google News + Facebook for spots AND events."""
    try:
        from services.scrapers.reviews_scraper import scrape_online_reviews
        from services.scrapers.social_scraper import scrape_social_all

        from services.scrapers.sentiment_analyzer import (
            analyze_all_external_reviews,
            analyze_all_feedbacks,
        )

        r1 = scrape_online_reviews()
        r2 = scrape_social_all()
        total = r1.get("inserted", 0) + r2.get("inserted", 0)
        errors = r1.get("errors", []) + r2.get("errors", [])
        s1 = analyze_all_feedbacks(force=False)
        s2 = analyze_all_external_reviews(force=False)
        labeled = s1.get("updated", 0) + s2.get("updated", 0)
        msg = (
            f"Reviews updated: {total} new review(s) scraped. "
            f"{labeled} new row(s) sentiment-labeled (existing labels kept)."
        )
        if errors:
            msg += f" ({len(errors)} scrape errors)"
        if not r2.get("ok"):
            msg += f" Note: {r2.get('error')}"
        flash(msg, "success")
    except Exception as exc:
        flash(f"Reviews scrape error: {exc}", "danger")
    from services.decision_support_service import invalidate_cache

    invalidate_cache()
    return redirect(url_for("dashboard.decision_support"))


@dashboard_bp.route("/actions/generate/insights", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def generate_insights():
    """AI-generate spot/event insights for entities not yet cached."""
    try:
        from services.scrapers.insights_generator import run_insights_generation

        result = run_insights_generation(force=False)
        generated = result.get("generated", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors") or []
        if generated > 0:
            msg = (
                f"AI insights generated for {generated} spot/event(s). "
                f"{skipped} already cached (skipped)."
            )
            flash(msg, "success")
        elif skipped > 0:
            flash(
                "All insights are already saved in the database. "
                "No regeneration needed.",
                "info",
            )
        else:
            flash(
                "No new insights to generate. Label sentiment first, "
                "then ensure spots/events have negative feedback.",
                "warning",
            )
        if errors:
            flash(f"{len(errors)} save error(s): {errors[0][:100]}", "warning")
    except Exception as exc:
        flash(f"Insights generation error: {exc}", "danger")
    from services.decision_support_service import invalidate_cache

    invalidate_cache()
    return redirect(url_for("dashboard.decision_support"))


# ---------------------------------------------------------------------------
# Review photo moderation (spot & event feedback images)
# ---------------------------------------------------------------------------


def _lgu_admin_can_moderate(user, row_lgu_id) -> bool:
    if user["role"] == "super_admin":
        return True
    if user["role"] == "lgu_admin":
        return int(row_lgu_id or -1) == int(resolve_dashboard_lgu_id(user) or -2)
    return False


@dashboard_bp.route("/actions/feedback/<int:feedback_id>/approve-images", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "lgu_admin")
def approve_feedback_images(feedback_id: int):
    from services.feedbacks import get_feedback_for_moderation, set_feedback_images_approval

    user = get_current_dashboard_user()
    row = get_feedback_for_moderation(feedback_id)
    if not row:
        flash("Feedback not found.", "danger")
        return redirect(url_for("dashboard.feedback"))
    spot_lgu_id = (row.get("tourist_spots") or {}).get("lgu_id")
    if not _lgu_admin_can_moderate(user, spot_lgu_id):
        flash("You can only moderate feedback for your own LGU.", "danger")
        return redirect(url_for("dashboard.feedback"))

    set_feedback_images_approval(feedback_id, "approved")
    flash("Review photos approved and now visible on the site.", "success")
    return redirect(url_for("dashboard.feedback"))


@dashboard_bp.route("/actions/feedback/<int:feedback_id>/reject-images", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "lgu_admin")
def reject_feedback_images(feedback_id: int):
    from services.feedbacks import get_feedback_for_moderation, set_feedback_images_approval

    user = get_current_dashboard_user()
    row = get_feedback_for_moderation(feedback_id)
    if not row:
        flash("Feedback not found.", "danger")
        return redirect(url_for("dashboard.feedback"))
    spot_lgu_id = (row.get("tourist_spots") or {}).get("lgu_id")
    if not _lgu_admin_can_moderate(user, spot_lgu_id):
        flash("You can only moderate feedback for your own LGU.", "danger")
        return redirect(url_for("dashboard.feedback"))

    set_feedback_images_approval(feedback_id, "rejected")
    flash("Review photos rejected and hidden from the site.", "info")
    return redirect(url_for("dashboard.feedback"))


@dashboard_bp.route("/actions/event-feedback/<int:feedback_id>/approve-images", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "lgu_admin")
def approve_event_feedback_images(feedback_id: int):
    from services.event_engagement import (
        get_event_feedback_for_moderation,
        set_event_feedback_images_approval,
    )

    user = get_current_dashboard_user()
    row = get_event_feedback_for_moderation(feedback_id)
    if not row:
        flash("Feedback not found.", "danger")
        return redirect(url_for("dashboard.feedback"))
    event_lgu_id = (row.get("events") or {}).get("lgu_id")
    if not _lgu_admin_can_moderate(user, event_lgu_id):
        flash("You can only moderate feedback for your own LGU.", "danger")
        return redirect(url_for("dashboard.feedback"))

    set_event_feedback_images_approval(feedback_id, "approved")
    flash("Review photos approved and now visible on the site.", "success")
    return redirect(url_for("dashboard.feedback"))


@dashboard_bp.route("/actions/event-feedback/<int:feedback_id>/reject-images", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "lgu_admin")
def reject_event_feedback_images(feedback_id: int):
    from services.event_engagement import (
        get_event_feedback_for_moderation,
        set_event_feedback_images_approval,
    )

    user = get_current_dashboard_user()
    row = get_event_feedback_for_moderation(feedback_id)
    if not row:
        flash("Feedback not found.", "danger")
        return redirect(url_for("dashboard.feedback"))
    event_lgu_id = (row.get("events") or {}).get("lgu_id")
    if not _lgu_admin_can_moderate(user, event_lgu_id):
        flash("You can only moderate feedback for your own LGU.", "danger")
        return redirect(url_for("dashboard.feedback"))

    set_event_feedback_images_approval(feedback_id, "rejected")
    flash("Review photos rejected and hidden from the site.", "info")
    return redirect(url_for("dashboard.feedback"))


@dashboard_bp.route("/actions/analyze/sentiment", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def run_sentiment_analysis():
    try:
        from services.scrapers.sentiment_analyzer import (
            analyze_all_external_reviews,
            analyze_all_feedbacks,
        )

        r1 = analyze_all_feedbacks(force=False)
        r2 = analyze_all_external_reviews(force=False)
        flash(
            f"Sentiment analysis complete: "
            f"{r1.get('updated', 0)} new spot feedbacks and "
            f"{r2.get('updated', 0)} new online reviews labeled "
            f"(existing labels were kept).",
            "success",
        )
    except Exception as exc:
        flash(f"Sentiment analysis error: {exc}", "danger")
    from services.decision_support_service import invalidate_cache

    invalidate_cache()
    return redirect(url_for("dashboard.decision_support"))
