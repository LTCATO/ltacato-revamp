# pyrefly: ignore [missing-import]
from flask import flash, redirect, request, url_for

from routes.dashboard.blueprint import dashboard_bp
from routes.dashboard.helpers import dashboard_login_required, role_required
from services.supabase_client import get_supabase
from services.dashboard_auth import (
    assign_profile_lgu_id,
    get_current_dashboard_user,
    resolve_dashboard_lgu_id,
)


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
    form_type = request.form.get("form_type", "record")
    if form_type == "arrival_report":
        return _save_arrival_report()
    if form_type == "site_update":
        return _save_site_update()
    flash(f"{form_type.replace('_', ' ').title()} saved successfully.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))


def _save_arrival_report():
    from services.arrival_reports import create_arrival_report, spot_ids_for_lgu
    from services.spots import list_spots_for_dashboard

    user = get_current_dashboard_user()
    role = user["role"]
    visitor_category = request.form.get("visitor_category", "day_tour")
    if visitor_category not in ("day_tour", "overnight"):
        flash("Invalid visitor category.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    report_type = request.form.get("report_type", "").strip()
    report_date = request.form.get("report_date", "").strip()
    if not report_type or not report_date:
        flash("Report type and date are required.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    allowed_types: tuple[str, ...]
    if role == "establishment_owner":
        allowed_types = ("daily", "weekly")
    elif role == "lgu_admin":
        allowed_types = ("monthly",)
    else:
        flash("Your role cannot submit arrival reports.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    if report_type not in allowed_types:
        flash(f"Invalid report type for your role.", "danger")
        return redirect(url_for("dashboard.arrivals"))

    lgu_id = resolve_dashboard_lgu_id(user)
    spot_id_raw = request.form.get("tourist_spot_id")
    tourist_spot_id = int(spot_id_raw) if spot_id_raw else None

    if role == "establishment_owner":
        owned = list_spots_for_dashboard(owner_id=user.get("id"), limit=20)
        owned_ids = {int(s["id"]) for s in owned if s.get("id") is not None}
        if not tourist_spot_id or tourist_spot_id not in owned_ids:
            flash("Select a valid establishment for this report.", "danger")
            return redirect(url_for("dashboard.arrivals"))
        spot = next((s for s in owned if int(s["id"]) == tourist_spot_id), None)
        lgu_id = spot.get("lgu_id") if spot else lgu_id
    elif role == "lgu_admin":
        if not lgu_id:
            form_lgu = request.form.get("lgu_id", "").strip()
            if form_lgu.isdigit():
                lgu_id = int(form_lgu)
                assign_profile_lgu_id(str(user.get("id")), lgu_id)
            else:
                flash(
                    "Your account is not linked to an LGU yet. Select your city/municipality "
                    "in the form, or ask LTCATO staff to set lgu_id on your profile.",
                    "danger",
                )
                return redirect(url_for("dashboard.arrivals"))
        allowed_spots = spot_ids_for_lgu(int(lgu_id))
        if not tourist_spot_id or tourist_spot_id not in allowed_spots:
            flash("Select a tourist spot that belongs to your LGU.", "danger")
            return redirect(url_for("dashboard.arrivals"))
    else:
        return redirect(url_for("dashboard.arrivals"))

    count_fields = (
        "this_city_male", "this_city_female", "other_city_male", "other_city_female",
        "other_province_male", "other_province_female", "foreign_male", "foreign_female",
    )
    payload: dict = {
        "tourist_spot_id": tourist_spot_id,
        "lgu_id": int(lgu_id) if lgu_id else None,
        "submitted_by": user.get("id"),
        "report_type": report_type,
        "report_date": report_date,
        "visitor_category": visitor_category,
        "overnight_nights": int(request.form.get("overnight_nights") or 0),
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
        flash(f"{label} {report_type} report saved.", "success")
    except Exception as exc:
        flash(f"Could not save report: {exc}", "danger")
    return redirect(url_for("dashboard.arrivals"))

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
        response = get_supabase().auth.admin.create_user({
            "email": email,
            "password": "ltcato@2026",
            "email_confirm": True,
            "user_metadata": {
                "first_name": first_name,
                "last_name": last_name,
                "role": "establishment_owner",
                "lgu_id": lgu_id_int,
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
                "lgu_id": lgu_id_int,
                "position": position,
            }).execute()

        flash(f"Establishment owner account created for {email} with default password ltcato@2026", "success")
    except Exception as e:
        flash(f"Failed to create owner account: {str(e)}", "danger")

    return redirect(request.referrer or url_for("dashboard.tourist_spots"))


@dashboard_bp.route("/actions/spot/register", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def register_establishment_spot():
    from services.spots import create_tourist_spot_for_owner, list_spots_for_dashboard, owner_has_spot

    user = get_current_dashboard_user()
    owner_id = str(user.get("id") or "")
    if owner_has_spot(owner_id):
        flash("You already have a registered establishment.", "info")
        return redirect(url_for("dashboard.site_updates"))

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
    from services.spots import claim_tourist_spot_for_owner, owner_has_spot

    user = get_current_dashboard_user()
    owner_id = str(user.get("id") or "")
    if owner_has_spot(owner_id):
        flash("You already have a linked establishment.", "info")
        return redirect(url_for("dashboard.site_updates"))

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
