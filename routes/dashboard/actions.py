# pyrefly: ignore [missing-import]
from flask import flash, redirect, request, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required, role_required
from services.supabase_client import get_supabase
from services.dashboard_auth import get_current_dashboard_user


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

@dashboard_bp.route("/actions/accounts/staff", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def create_staff_account():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    position = request.form.get("position", "").strip()

    try:
        response = get_supabase().auth.admin.create_user({
            "email": email,
            "password": "ltcato@2026",
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": "ltcato_staff"
            }
        })
        user = response.user
        
        # Insert into profiles
        role_res = get_supabase().table("roles").select("id").eq("role_key", "ltcato_staff").execute()
        if role_res.data:
            role_id = role_res.data[0]["id"]
            get_supabase().table("profiles").upsert({
                "id": user.id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "role_id": role_id,
                "position": position
            }).execute()

        flash(f"LTCATO staff account created for {email} with default password ltcato@2026", "success")
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

    try:
        response = get_supabase().auth.admin.create_user({
            "email": email,
            "password": "ltcato@2026",
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": "lgu_admin",
                "lgu_id": int(lgu_id) if lgu_id else None
            }
        })
        user = response.user
        
        # Insert into profiles
        role_res = get_supabase().table("roles").select("id").eq("role_key", "lgu_admin").execute()
        if role_res.data:
            role_id = role_res.data[0]["id"]
            get_supabase().table("profiles").upsert({
                "id": user.id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "role_id": role_id,
                "lgu_id": int(lgu_id) if lgu_id else None,
                "position": position
            }).execute()

        flash(f"LGU account created for {email} with default password ltcato@2026", "success")
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
    
    user = get_current_dashboard_user()
    lgu_id = request.form.get("lgu_id")
    if user["role"] == "lgu_admin":
        lgu_id = user.get("lgu_id")

    try:
        response = get_supabase().auth.admin.create_user({
            "email": email,
            "password": "ltcato@2026",
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": "establishment_owner",
                "lgu_id": int(lgu_id) if lgu_id else None
            }
        })
        new_user = response.user
        
        # Upsert into profiles
        role_res = get_supabase().table("roles").select("id").eq("role_key", "establishment_owner").execute()
        if role_res.data:
            role_id = role_res.data[0]["id"]
            get_supabase().table("profiles").upsert({
                "id": new_user.id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "role_id": role_id,
                "lgu_id": int(lgu_id) if lgu_id else None,
                "position": position
            }).execute()

        flash(f"Establishment owner account created for {email} with default password ltcato@2026", "success")
    except Exception as e:
        flash(f"Failed to create owner account: {str(e)}", "danger")

    return redirect(request.referrer or url_for("dashboard.tourist_spots"))
