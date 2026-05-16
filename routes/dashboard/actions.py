from flask import flash, redirect, request, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required, role_required
from services.supabase_client import get_supabase


@dashboard_bp.route("/actions/event/<int:event_id>/approve", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def approve_event(event_id: int):
    get_supabase().table("events").update({"approval_status": "approved"}).eq("id", event_id).execute()
    flash("Event approved and can appear on the public site.", "success")
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/event/<int:event_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def reject_event(event_id: int):
    get_supabase().table("events").update({"approval_status": "rejected"}).eq("id", event_id).execute()
    flash("Event rejected.", "info")
    return redirect(url_for("dashboard.promotions"))


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/approve", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def approve_chatbot(entry_id: int):
    get_supabase().table("chatbot_knowledge").update({"approval_status": "approved"}).eq("id", entry_id).execute()
    flash("FAQ entry approved for the chatbot.", "success")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def reject_chatbot(entry_id: int):
    get_supabase().table("chatbot_knowledge").update({"approval_status": "rejected"}).eq("id", entry_id).execute()
    flash("FAQ entry rejected.", "info")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/spot/<int:spot_id>/approve-ltcato", methods=["POST"])
@dashboard_login_required
@role_required("ltcato_staff")
def approve_spot_ltcato(spot_id: int):
    get_supabase().table("tourist_spots").update({"approval_status": "approved"}).eq("id", spot_id).execute()
    flash("Tourist spot approved for the public directory.", "success")
    return redirect(url_for("dashboard.lgu_management"))


@dashboard_bp.route("/actions/spot/<int:spot_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("ltcato_staff")
def reject_spot(spot_id: int):
    get_supabase().table("tourist_spots").update({"approval_status": "rejected"}).eq("id", spot_id).execute()
    flash("Tourist spot rejected.", "info")
    return redirect(url_for("dashboard.lgu_management"))


@dashboard_bp.route("/actions/form/save", methods=["POST"])
@dashboard_login_required
def form_save_stub():
    """Placeholder for modal form submissions until full CRUD is wired."""
    form_type = request.form.get("form_type", "record")
    flash(f"{form_type.replace('_', ' ').title()} saved successfully.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))
