"""
Google Trends scraper via pytrends (no API key).
NOTE: Google rate-limits aggressively (429). If you get errors, wait 1-2 hours.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from services.supabase_client import get_supabase

# Base keywords always included
_BASE_KEYWORDS: list[str] = [
    "Laguna tourism",
    "Laguna Philippines travel",
    "DOT Philippines tourism",
]
BATCH_SIZE = 5


def _build_keywords() -> list[str]:
    """Build keyword list from actual approved tourist spot names + base keywords."""
    try:
        from services.supabase_client import get_supabase as _sb

        spots = (
            _sb()
            .table("tourist_spots")
            .select("name")
            .eq("approval_status", "approved")
            .limit(7)
            .execute()
            .data
            or []
        )
        spot_names = [s["name"] for s in spots if s.get("name")]
    except Exception:
        spot_names = []
    # Combine spot names with base keywords, max 10 total (2 batches of 5)
    keywords = spot_names[:7] + _BASE_KEYWORDS
    return keywords[:10]


def scrape_trends() -> dict[str, Any]:
    try:
        from pytrends.request import TrendReq  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "error": "pytrends not installed. Run: pip install pytrends",
            "inserted": 0,
        }

    keywords = _build_keywords()
    pytrends = TrendReq(hl="en-PH", tz=480, timeout=(10, 30))
    inserted = 0
    errors: list[str] = []
    batches = [
        keywords[i : i + BATCH_SIZE] for i in range(0, len(keywords), BATCH_SIZE)
    ]

    for batch in batches:
        try:
            pytrends.build_payload(batch, cat=67, timeframe="today 3-m", geo="PH")
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                errors.append(f"No data for: {batch}")
                time.sleep(2)
                continue
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            non_zero = df[(df > 0).any(axis=1)]
            target_row = non_zero.iloc[-1] if not non_zero.empty else df.iloc[-1]
            trend_date = (
                (non_zero.index[-1] if not non_zero.empty else df.index[-1])
                .date()
                .isoformat()
            )

            related_map: dict = {}
            try:
                time.sleep(1)
                related_map = pytrends.related_queries() or {}
            except Exception:
                pass

            for keyword in batch:
                if keyword not in df.columns:
                    continue
                interest_val = int(target_row.get(keyword, 0))
                related_queries: list = []
                kw_rel = related_map.get(keyword) or {}
                top_df = kw_rel.get("top")
                if top_df is not None and not getattr(top_df, "empty", True):
                    try:
                        related_queries = (
                            top_df.head(5)
                            .rename(columns={"query": "q", "value": "v"})
                            .to_dict("records")
                        )
                    except Exception:
                        pass
                try:
                    get_supabase().table("scraped_trends").insert(
                        {
                            "keyword": keyword,
                            "region": "PH",
                            "interest_value": interest_val,
                            "trend_date": trend_date,
                            "related_queries": related_queries,
                            "scraped_at": datetime.utcnow().isoformat(),
                        }
                    ).execute()
                    inserted += 1
                except Exception as exc:
                    errors.append(f"{keyword}: {exc}")
            time.sleep(2)
        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "TooManyRequests" in err_str:
                errors.append(
                    f"Rate limited by Google (429). Wait 1-2 hours before retrying. Batch: {batch}"
                )
            else:
                errors.append(f"Batch {batch}: {exc}")

    return {"ok": True, "inserted": inserted, "errors": errors}


def get_latest_trends(limit: int = 10) -> list[dict]:
    try:
        return (
            get_supabase()
            .table("scraped_trends")
            .select("id,keyword,interest_value,trend_date,related_queries,scraped_at")
            .order("scraped_at", desc=True)
            .order("interest_value", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        return []
