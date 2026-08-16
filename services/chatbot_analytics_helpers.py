"""
Deterministic calculations over data already returned by dashboard_analytics.py.

Pure functions only — no DB/network access, and dashboard_analytics.py is
never modified. This is what lets LARA state a growth percentage without
ever asking the LLM to compute (and possibly invent) one.
"""

from __future__ import annotations

from typing import Any

_DECLINE_THRESHOLD_PCT = -15.0
_RISE_THRESHOLD_PCT = 15.0


def _pct_change(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def compute_growth_pct(monthly_trend: list[dict[str, Any]]) -> dict[str, Any]:
    """
    monthly_trend: [{"month": "YYYY-MM", "visitors": int}, ...] sorted oldest->newest,
    as returned by services.dashboard_analytics._monthly_trend().
    """
    months = [m for m in (monthly_trend or []) if m.get("month")]
    if not months:
        return {
            "available": False,
            "current_month": None,
            "current_total": 0,
            "previous_month": None,
            "previous_total": 0,
            "mom_growth_pct": None,
            "first_vs_last_growth_pct": None,
            "direction": "flat",
        }

    current = months[-1]
    previous = months[-2] if len(months) >= 2 else None

    mom_growth = (
        _pct_change(current.get("visitors", 0), previous.get("visitors", 0))
        if previous
        else None
    )
    first_vs_last = (
        _pct_change(months[-1].get("visitors", 0), months[0].get("visitors", 0))
        if len(months) >= 2
        else None
    )

    direction = "flat"
    reference = mom_growth if mom_growth is not None else first_vs_last
    if reference is not None:
        if reference <= _DECLINE_THRESHOLD_PCT:
            direction = "declining"
        elif reference >= _RISE_THRESHOLD_PCT:
            direction = "rising"

    return {
        "available": True,
        "current_month": current.get("month"),
        "current_total": current.get("visitors", 0),
        "previous_month": previous.get("month") if previous else None,
        "previous_total": previous.get("visitors", 0) if previous else 0,
        "mom_growth_pct": mom_growth,
        "first_vs_last_growth_pct": first_vs_last,
        "direction": direction,
    }
