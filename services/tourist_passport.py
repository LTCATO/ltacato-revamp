"""
Laguna tourist passport — stamps and points for visited spots.
"""

from __future__ import annotations

import random
import string
from typing import Any

from services.supabase_client import get_supabase

PASSPORT_FIELDS = "id, passport_number, points, created_at"
STAMP_FIELDS = (
    "id, stamped_at, tourist_spots(id, name, main_image_url, lgus(id, name))"
)


def _generate_passport_number() -> str:
    suffix = "".join(random.choices(string.digits, k=6))
    return f"LAG-{suffix}"


def get_or_create_passport(tourist_id: str) -> dict[str, Any] | None:
    try:
        existing = (
            get_supabase()
            .table("tourist_passports")
            .select(PASSPORT_FIELDS)
            .eq("tourist_id", tourist_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

        for _ in range(5):
            number = _generate_passport_number()
            try:
                ins = (
                    get_supabase()
                    .table("tourist_passports")
                    .insert(
                        {
                            "tourist_id": tourist_id,
                            "passport_number": number,
                            "points": 0,
                        }
                    )
                    .execute()
                )
                if ins.data:
                    return ins.data[0]
            except Exception:
                continue
    except Exception:
        pass
    return None


def list_passport_stamps(passport_id: int, limit: int = 50) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("passport_stamps")
        .select(STAMP_FIELDS)
        .eq("passport_id", passport_id)
        .order("stamped_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def stamp_spot(passport_id: int, tourist_spot_id: int, *, points: int = 10) -> bool:
    """Record a visit stamp if not already stamped for this spot."""
    try:
        dup = (
            get_supabase()
            .table("passport_stamps")
            .select("id")
            .eq("passport_id", passport_id)
            .eq("tourist_spot_id", tourist_spot_id)
            .limit(1)
            .execute()
        )
        if dup.data:
            return True

        get_supabase().table("passport_stamps").insert(
            {"passport_id": passport_id, "tourist_spot_id": tourist_spot_id}
        ).execute()

        passport = (
            get_supabase()
            .table("tourist_passports")
            .select("points")
            .eq("id", passport_id)
            .single()
            .execute()
        )
        current = (passport.data or {}).get("points") or 0
        get_supabase().table("tourist_passports").update({"points": current + points}).eq(
            "id", passport_id
        ).execute()
        return True
    except Exception:
        return False
