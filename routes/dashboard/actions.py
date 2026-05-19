# pyrefly: ignore [missing-import]
from flask import flash, redirect, request, url_for

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
    get_supabase().table("chatbot_knowledge").update(
        {"approval_status": "approved"}
    ).eq("id", entry_id).execute()
    flash("FAQ entry approved for the chatbot.", "success")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/chatbot/<int:entry_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("super_admin")
def reject_chatbot(entry_id: int):
    get_supabase().table("chatbot_knowledge").update(
        {"approval_status": "rejected"}
    ).eq("id", entry_id).execute()
    flash("FAQ entry rejected.", "info")
    return redirect(url_for("dashboard.chatbot"))


@dashboard_bp.route("/actions/spot/<int:spot_id>/approve-ltcato", methods=["POST"])
@dashboard_login_required
@role_required("ltcato_staff")
def approve_spot_ltcato(spot_id: int):
    get_supabase().table("tourist_spots").update({"approval_status": "approved"}).eq(
        "id", spot_id
    ).execute()
    flash("Tourist spot approved for the public directory.", "success")
    return redirect(url_for("dashboard.lgu_management"))


@dashboard_bp.route("/actions/spot/<int:spot_id>/reject", methods=["POST"])
@dashboard_login_required
@role_required("ltcato_staff")
def reject_spot(spot_id: int):
    get_supabase().table("tourist_spots").update({"approval_status": "rejected"}).eq(
        "id", spot_id
    ).execute()
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
@role_required("ltcato_staff")
def save_event():
    from services.events import create_event_from_request

    user = get_current_dashboard_user()
    try:
        create_event_from_request(
            request.form, request.files, created_by=str(user.get("id") or "")
        )
        flash("Event published successfully.", "success")
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


@dashboard_bp.route("/actions/accounts/staff", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def create_staff_account():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip()
    position = request.form.get("position", "").strip()

    try:
        response = get_supabase().auth.admin.create_user(
            {
                "email": email,
                "password": "ltcato@2026",
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
            f"LTCATO staff account created for {email} with default password ltcato@2026",
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

    try:
        response = get_supabase().auth.admin.create_user(
            {
                "email": email,
                "password": "ltcato@2026",
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
            f"LGU account created for {email} with default password ltcato@2026",
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
            f"Establishment owner account created for {email} with default password ltcato@2026",
            "success",
        )
    except Exception as e:
        flash(f"Failed to create owner account: {str(e)}", "danger")

    return redirect(request.referrer or url_for("dashboard.tourist_spots"))


@dashboard_bp.route("/actions/spot/register", methods=["POST"])
@dashboard_login_required
@role_required("establishment_owner")
def register_establishment_spot():
    from services.spots import (
        create_tourist_spot_for_owner,
        list_spots_for_dashboard,
        owner_has_spot,
    )

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


# ---------------------------------------------------------------------------
# Decision Support — scraper trigger routes
# ---------------------------------------------------------------------------


@dashboard_bp.route("/actions/scrape/weather", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def scrape_weather():
    try:
        from services.scrapers.weather_scraper import scrape_weather_for_lgus

        result = scrape_weather_for_lgus()
        if result.get("ok"):
            msg = f"Weather updated: {result['inserted']} LGU records inserted."
            if result.get("errors"):
                msg += f" ({len(result['errors'])} errors)"
            flash(msg, "success")
        else:
            flash(f"Weather scrape failed: {result.get('error')}", "danger")
    except Exception as exc:
        flash(f"Weather scrape error: {exc}", "danger")
    from services.decision_support_service import invalidate_cache

    invalidate_cache()
    return redirect(url_for("dashboard.decision_support"))


@dashboard_bp.route("/actions/scrape/news", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def scrape_news():
    try:
        from services.scrapers.news_scraper import scrape_news as _scrape

        result = _scrape()
        if result.get("ok"):
            msg = f"News updated: {result['inserted']} new articles scraped."
            if result.get("errors"):
                msg += f" ({len(result['errors'])} errors ignored)"
            flash(msg, "success")
        else:
            flash(f"News scrape failed: {result.get('error')}", "danger")
    except Exception as exc:
        flash(f"News scrape error: {exc}", "danger")
    from services.decision_support_service import invalidate_cache

    invalidate_cache()
    return redirect(url_for("dashboard.decision_support"))


@dashboard_bp.route("/actions/scrape/trends", methods=["POST"])
@dashboard_login_required
@role_required("super_admin", "ltcato_staff")
def scrape_trends():
    try:
        from services.scrapers.trends_scraper import scrape_trends as _scrape

        result = _scrape()
        if result.get("ok"):
            errors = result.get("errors", [])
            if result["inserted"] > 0:
                msg = f"Trends updated: {result['inserted']} keyword records inserted."
                if errors:
                    msg += f" ({len(errors)} minor errors)"
                flash(msg, "success")
            elif errors:
                # Check if it's a rate-limit error
                first_err = errors[0] if errors else ""
                if "429" in first_err or "rate" in first_err.lower():
                    flash(
                        "Google Trends rate-limited (429). Wait 1–2 hours then try again. "
                        "This is a Google restriction, not a system error.",
                        "warning",
                    )
                else:
                    flash(
                        f"Trends: 0 inserted. First error: {first_err[:120]}", "warning"
                    )
            else:
                flash(
                    "Trends: 0 records inserted (no data returned from Google).", "info"
                )
        else:
            flash(f"Trends scrape failed: {result.get('error')}", "danger")
    except Exception as exc:
        flash(f"Trends scrape error: {exc}", "danger")
    from services.decision_support_service import invalidate_cache

    invalidate_cache()
    return redirect(url_for("dashboard.decision_support"))


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
