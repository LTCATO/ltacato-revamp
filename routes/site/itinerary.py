from __future__ import annotations

import json
import os
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.itineraries import (
    delete_itinerary,
    get_itinerary,
    get_spots_by_ids,
    list_planner_spots,
    list_user_itineraries,
    plan_from_itinerary_row,
    save_itinerary_from_plan,
)
from services.itinerary_planner import generate_plan, planner_form_options
from services.tourist_auth import get_current_tourist
from services.tourist_passport import get_or_create_passport, stamp_spot
from utils.jinja_helpers import normalize_image_url
from utils.tourist_helpers import tourist_login_required

itinerary_bp = Blueprint("itinerary", __name__)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _form_int(name: str, default: int = 0) -> int:
    raw = request.form.get(name) or request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _form_float(name: str) -> float | None:
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _selected_spot_ids() -> list[int]:
    ids: list[int] = []
    for raw in request.form.getlist("spot_ids"):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    preselect = request.args.get("spot_id") or request.form.get("preselect_spot_id")
    if preselect:
        try:
            sid = int(preselect)
            if sid not in ids:
                ids.append(sid)
        except (TypeError, ValueError):
            pass
    return ids


def _spot_priorities() -> dict[int, str]:
    priorities: dict[int, str] = {}
    for key, value in request.form.items():
        if key.startswith("priority_"):
            try:
                sid = int(key.replace("priority_", ""))
                if value in ("must_visit", "optional", "skip_if_needed"):
                    priorities[sid] = value
            except ValueError:
                continue
    return priorities


def _build_plan_from_request() -> dict:
    start = _parse_date(request.form.get("start_date"))
    end = _parse_date(request.form.get("end_date"))
    if not start:
        start = date.today()
    if not end:
        end = start
    if end < start:
        end = start

    spot_ids = _selected_spot_ids()
    spots = get_spots_by_ids(spot_ids)

    category_ids = []
    for raw in request.form.getlist("category_ids"):
        try:
            category_ids.append(int(raw))
        except (TypeError, ValueError):
            pass

    return generate_plan(
        title=(request.form.get("title") or "My Laguna Trip").strip(),
        spots=spots,
        start_date=start,
        end_date=end,
        starting_point=(request.form.get("starting_point") or "").strip(),
        starting_lat=_form_float("starting_lat"),
        starting_lng=_form_float("starting_lng"),
        departure_time=(request.form.get("departure_time") or "08:00").strip(),
        return_time=(request.form.get("return_time") or "18:00").strip(),
        traveler_count=max(1, _form_int("traveler_count", 1)),
        trip_purpose=(request.form.get("trip_purpose") or "vacation").strip(),
        total_budget=_form_float("total_budget"),
        pace=(request.form.get("pace") or "moderate").strip(),
        route_style=(request.form.get("route_style") or "shortest").strip(),
        category_ids=category_ids or None,
        lgu_id=_form_int("lgu_id") or None,
        spot_priorities=_spot_priorities(),
        notes=(request.form.get("notes") or "").strip(),
    )


def _planner_context(
    *,
    plan: dict | None = None,
    form_values: dict | None = None,
    selected_spot_ids: list[int] | None = None,
) -> dict:
    options = planner_form_options()
    q = (request.args.get("q") or request.form.get("q") or "").strip()
    category_id = _form_int("category_id") or None
    lgu_id = _form_int("lgu_id") or None
    if not category_id and request.args.get("category"):
        category_id = _form_int("category") or None

    spots = list_planner_spots(q=q or None, category_id=category_id, lgu_id=lgu_id)
    selected = set(selected_spot_ids or _selected_spot_ids())

    form_values = form_values or {
        "title": request.form.get("title") or "My Laguna Adventure",
        "start_date": request.form.get("start_date") or date.today().isoformat(),
        "end_date": request.form.get("end_date") or (date.today() + timedelta(days=2)).isoformat(),
        "departure_time": request.form.get("departure_time") or "08:00",
        "return_time": request.form.get("return_time") or "18:00",
        "starting_point": request.form.get("starting_point") or "",
        "starting_lat": request.form.get("starting_lat") or "",
        "starting_lng": request.form.get("starting_lng") or "",
        "traveler_count": _form_int("traveler_count", 1) or 1,
        "trip_purpose": request.form.get("trip_purpose") or "vacation",
        "total_budget": request.form.get("total_budget") or "",
        "pace": request.form.get("pace") or "moderate",
        "route_style": request.form.get("route_style") or "shortest",
        "notes": request.form.get("notes") or "",
    }

    map_points = []
    for stop_day in (plan or {}).get("days") or []:
        for stop in stop_day.get("stops") or []:
            if stop.get("latitude") and stop.get("longitude"):
                map_points.append(
                    {
                        "lat": float(stop["latitude"]),
                        "lng": float(stop["longitude"]),
                        "name": stop.get("name"),
                    }
                )

    all_spots_json = []
    for s in spots:
        try:
            lat = float(s.get("latitude"))
            lng = float(s.get("longitude"))
            cat = s.get("attraction_categories")
            cat_name = cat.get("name") if isinstance(cat, dict) else ""
            all_spots_json.append({
                "id": s["id"],
                "name": s["name"],
                "lat": lat,
                "lng": lng,
                "category_name": cat_name
            })
        except (TypeError, ValueError, AttributeError):
            continue

    return {
        **options,
        "spots": spots,
        "selected_spot_ids": selected,
        "form_values": form_values,
        "plan": plan,
        "plan_json": json.dumps(plan) if plan else "",
        "active_q": q,
        "active_category": category_id,
        "active_lgu": lgu_id,
        "map_points": map_points,
        "all_spots_json": all_spots_json,
        "map_api_key": (os.getenv("MAP_API_KEY") or "").strip(),
    }


@itinerary_bp.route("/planner", methods=["GET", "POST"])
def planner():
    tourist = get_current_tourist()
    preselect = request.args.get("spot_id", type=int)

    if request.method == "POST":
        action = (request.form.get("action") or "generate").strip()

        if action == "save":
            if not tourist:
                flash("Sign in to save your itinerary.", "warning")
                return redirect(url_for("auth.login", next=url_for("itinerary.planner")))

            plan_raw = request.form.get("plan_json")
            try:
                plan = json.loads(plan_raw) if plan_raw else _build_plan_from_request()
            except json.JSONDecodeError:
                plan = _build_plan_from_request()

            if not plan.get("ok"):
                flash(plan.get("error") or "Could not build itinerary.", "danger")
                ctx = _planner_context(plan=None)
                return render_template("views/site/itinerary/planner.html", **ctx)

            ok, saved_id, err = save_itinerary_from_plan(tourist["id"], plan)
            if ok and saved_id:
                flash("Your itinerary has been saved.", "success")
                return redirect(url_for("itinerary.itinerary_detail", itinerary_id=saved_id))
            flash(err or "Save failed.", "danger")

        plan = _build_plan_from_request()
        if not plan.get("ok"):
            flash(plan.get("error") or "Could not generate itinerary.", "danger")
            ctx = _planner_context(plan=None, selected_spot_ids=_selected_spot_ids())
            return render_template("views/site/itinerary/planner.html", **ctx)

        ctx = _planner_context(plan=plan, selected_spot_ids=_selected_spot_ids())
        return render_template("views/site/itinerary/planner.html", **ctx)

    selected_ids = [preselect] if preselect else []
    ctx = _planner_context(selected_spot_ids=selected_ids)
    return render_template("views/site/itinerary/planner.html", **ctx)


@itinerary_bp.route("/my-trips")
@tourist_login_required
def my_itineraries():
    tourist = get_current_tourist()
    assert tourist
    trips = list_user_itineraries(tourist["id"])
    return render_template(
        "views/site/itinerary/list.html",
        trips=trips,
    )


@itinerary_bp.route("/my-trips/<int:itinerary_id>")
@tourist_login_required
def itinerary_detail(itinerary_id: int):
    tourist = get_current_tourist()
    assert tourist
    row = get_itinerary(itinerary_id, tourist["id"])
    if not row:
        abort(404)

    plan = plan_from_itinerary_row(row)
    map_points = []
    for day in plan.get("days") or []:
        for stop in day.get("stops") or []:
            if stop.get("latitude") and stop.get("longitude"):
                map_points.append(
                    {
                        "lat": float(stop["latitude"]),
                        "lng": float(stop["longitude"]),
                        "name": stop.get("name"),
                    }
                )

    passport = get_or_create_passport(tourist["id"])

    return render_template(
        "views/site/itinerary/detail.html",
        itinerary=row,
        plan=plan,
        map_points=map_points,
        passport=passport,
        show_passport_stamps=True,
        stamp_itinerary_id=itinerary_id,
    )


@itinerary_bp.route("/my-trips/<int:itinerary_id>/stamp/<int:spot_id>", methods=["POST"])
@tourist_login_required
def itinerary_stamp(itinerary_id: int, spot_id: int):
    tourist = get_current_tourist()
    assert tourist
    row = get_itinerary(itinerary_id, tourist["id"])
    if not row:
        abort(404)
    passport = get_or_create_passport(tourist["id"])
    if passport and stamp_spot(passport["id"], spot_id):
        flash("Laguna passport stamp collected!", "success")
    else:
        flash("Could not collect stamp.", "danger")
    return redirect(url_for("itinerary.itinerary_detail", itinerary_id=itinerary_id))


@itinerary_bp.route("/my-trips/<int:itinerary_id>/delete", methods=["POST"])
@tourist_login_required
def itinerary_delete(itinerary_id: int):
    tourist = get_current_tourist()
    assert tourist
    if delete_itinerary(itinerary_id, tourist["id"]):
        flash("Itinerary deleted.", "info")
    else:
        flash("Could not delete itinerary.", "danger")
    return redirect(url_for("itinerary.my_itineraries"))
