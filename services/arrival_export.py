"""
Fill official DOT arrival Excel templates from Supabase monthly per-spot reports.
"""

from __future__ import annotations

import io
import re
from calendar import month_name
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl

from services.arrival_reports import monthly_spot_reports_for_export
from services.lgus import list_lgus_simple

_STATIC = Path(__file__).resolve().parent.parent / "static" / "excel"
DAY_TOUR_TEMPLATE = _STATIC / "DTA3 (VAR2).xlsx"
OVERNIGHT_TEMPLATE = _STATIC / "DAE3B_FORM_A_City_Muni.xlsx"

_COUNT_KEYS = (
    "this_city_male",
    "this_city_female",
    "other_city_male",
    "other_city_female",
    "other_province_male",
    "other_province_female",
    "foreign_male",
    "foreign_female",
)


def _parse_report_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return date.today()


def _lgu_name(row: dict[str, Any]) -> str:
    lgu = row.get("lgus") or {}
    if isinstance(lgu, dict) and lgu.get("name"):
        return str(lgu["name"])
    return ""


def _spot_name(row: dict[str, Any]) -> str:
    spot = row.get("tourist_spots") or {}
    if isinstance(spot, dict) and spot.get("name"):
        return str(spot["name"])
    return f"Spot #{row.get('tourist_spot_id', '')}"


def _spot_code(row: dict[str, Any]) -> int | str | None:
    spot = row.get("tourist_spots") or {}
    if isinstance(spot, dict) and spot.get("code") is not None:
        return spot["code"]
    return None


def _month_year_label(report_date: date) -> str:
    return f"{month_name[report_date.month]} {report_date.year}"


def _month_column(report_date: date) -> int:
    return report_date.month + 1


def _safe_filename_part(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name.strip()).strip("_") or "LGU"


def _lgu_label(lgu_id: int) -> str:
    for row in list_lgus_simple():
        if int(row["id"]) == lgu_id:
            return str(row["name"])
    return f"LGU_{lgu_id}"


def export_day_tour_workbook(
    *,
    lgu_id: int,
    report_date: date | None = None,
) -> tuple[bytes, str]:
    reports = monthly_spot_reports_for_export(
        lgu_id=lgu_id,
        report_date=report_date,
        visitor_category="day_tour",
    )
    if not reports and report_date:
        reports = monthly_spot_reports_for_export(
            lgu_id=lgu_id,
            visitor_category="day_tour",
        )

    wb = openpyxl.load_workbook(DAY_TOUR_TEMPLATE)
    ws = wb.active
    lgu_title = _lgu_label(lgu_id)

    if reports:
        rd = _parse_report_date(reports[0].get("report_date"))
        ws["F5"] = _month_year_label(rd)
        ws["F6"] = _lgu_name(reports[0]) or lgu_title
        start_row = 12
        for i, rep in enumerate(reports[:50]):
            row = start_row + i
            ws.cell(row, 2, _spot_name(rep))
            code = _spot_code(rep)
            if code is not None:
                ws.cell(row, 3, code)
            ws.cell(row, 4, int(rep.get("this_city_male") or 0))
            ws.cell(row, 5, int(rep.get("this_city_female") or 0))
            ws.cell(row, 7, int(rep.get("other_city_male") or 0))
            ws.cell(row, 8, int(rep.get("other_city_female") or 0))
            ws.cell(row, 10, int(rep.get("other_province_male") or 0))
            ws.cell(row, 11, int(rep.get("other_province_female") or 0))
            ws.cell(row, 13, int(rep.get("foreign_male") or 0))
            if ws.max_column >= 14:
                ws.cell(row, 14, int(rep.get("foreign_female") or 0))
        totals = {
            k: sum(int(r.get(k) or 0) for r in reports)
            for k in _COUNT_KEYS
        }
        ws.cell(19, 4, totals["this_city_male"])
        ws.cell(19, 5, totals["this_city_female"])
        ws.cell(19, 7, totals["other_city_male"])
        ws.cell(19, 8, totals["other_city_female"])
        ws.cell(19, 10, totals["other_province_male"])
        ws.cell(19, 11, totals["other_province_female"])
        ws.cell(19, 13, totals["foreign_male"])
        if ws.max_column >= 14:
            ws.cell(19, 14, totals["foreign_female"])
    else:
        ws["F6"] = lgu_title

    buf = io.BytesIO()
    wb.save(buf)
    fname = f"DTA3_{_safe_filename_part(lgu_title)}_day_tour.xlsx"
    return buf.getvalue(), fname


def export_overnight_workbook(
    *,
    lgu_id: int,
    report_date: date | None = None,
) -> tuple[bytes, str]:
    reports = monthly_spot_reports_for_export(
        lgu_id=lgu_id,
        report_date=report_date,
        visitor_category="overnight",
    )
    if not reports and report_date:
        reports = monthly_spot_reports_for_export(
            lgu_id=lgu_id,
            visitor_category="overnight",
        )

    wb = openpyxl.load_workbook(OVERNIGHT_TEMPLATE)
    ws = wb["LGU FORM A by Country (Monthly)"]
    lgu_title = _lgu_label(lgu_id)

    if reports:
        rd = _parse_report_date(reports[0].get("report_date"))
        ws["B10"] = _lgu_name(reports[0]) or lgu_title
        ws["B5"] = _month_year_label(rd)
        col = _month_column(rd)
        ph_local = sum(
            int(r.get("this_city_male") or 0)
            + int(r.get("this_city_female") or 0)
            + int(r.get("other_city_male") or 0)
            + int(r.get("other_city_female") or 0)
            + int(r.get("other_province_male") or 0)
            + int(r.get("other_province_female") or 0)
            for r in reports
        )
        ph_foreign_nat = sum(
            int(r.get("foreign_male") or 0) + int(r.get("foreign_female") or 0)
            for r in reports
        )
        guest_nights = sum(int(r.get("overnight_nights") or 0) for r in reports)
        ws.cell(16, col, ph_local)
        ws.cell(17, col, ph_foreign_nat)
        ws.cell(18, col, guest_nights or (ph_local + ph_foreign_nat))
    else:
        ws["B10"] = lgu_title

    buf = io.BytesIO()
    wb.save(buf)
    fname = f"DAE3B_{_safe_filename_part(lgu_title)}_overnight.xlsx"
    return buf.getvalue(), fname
