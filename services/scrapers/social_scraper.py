"""
Social Media Scraper — Facebook posts via RapidAPI.
Searches Facebook for posts about Laguna tourist spots and events.

API: https://facebook-scraper3.p.rapidapi.com/search/posts
Key configured as RAPIDAPI_KEY in .env

Results are stored in external_reviews table:
  - Spot posts → tourist_spot_id set, event_id NULL
  - Event posts → event_id set, tourist_spot_id NULL
  (Requires event_id column in external_reviews — run the SQL migration first)
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import requests

from services.scrapers.sentiment_analyzer import analyze_sentiment
from services.supabase_client import get_supabase

RAPIDAPI_KEY = os.getenv(
    "RAPIDAPI_KEY", "5ff1bfc10cmshe5d845d6ee26d10p127e02jsn7b41af6d7ddd"
)
FB_SEARCH_URL = "https://facebook-scraper3.p.rapidapi.com/search/posts"
_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "facebook-scraper3.p.rapidapi.com",
}


def _fb_search(query: str) -> list[dict]:
    """Search Facebook posts for a query. Returns list of post dicts."""
    try:
        resp = requests.get(
            FB_SEARCH_URL,
            headers=_HEADERS,
            params={"query": query},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("results", [])[:5]  # Max 5 per query
    except Exception:
        pass
    return []


def _already_in_db(post_id: str) -> bool:
    """Check if a Facebook post already stored (by reviewer_name = post_id)."""
    if not post_id:
        return False
    try:
        return bool(
            get_supabase()
            .table("external_reviews")
            .select("id")
            .eq("reviewer_name", f"fb:{post_id}")
            .limit(1)
            .execute()
            .data
        )
    except Exception:
        return False


def _store_post(post: dict, tourist_spot_id: int | None, event_id: int | None) -> bool:
    """Parse a Facebook post dict and insert into external_reviews."""
    message = (post.get("message") or "").strip()
    if not message or len(message) < 20:
        return False

    post_id = post.get("post_id", "")
    if post_id and _already_in_db(post_id):
        return False

    author = post.get("author") or {}
    author_name = (
        author.get("name", "Facebook User")
        if isinstance(author, dict)
        else "Facebook User"
    )
    post_url = post.get("url", "")
    timestamp = post.get("timestamp") or post.get("time")

    sentiment_label, _ = analyze_sentiment(message)

    # Build source string with URL for linkability
    source = (
        f"Facebook | {post_url}" if post_url and len(post_url) < 490 else "Facebook"
    )

    record: dict[str, Any] = {
        "source": source[:500],
        "reviewer_name": f"fb:{post_id}" if post_id else author_name[:200],
        "review_text": message[:2000],
        "sentiment": sentiment_label,
        "review_date": timestamp or datetime.utcnow().isoformat(),
        "scraped_at": datetime.utcnow().isoformat(),
    }

    if tourist_spot_id:
        record["tourist_spot_id"] = tourist_spot_id
    if event_id:
        record["event_id"] = event_id

    try:
        get_supabase().table("external_reviews").insert(record).execute()
        return True
    except Exception:
        return False


def scrape_spots_social() -> dict[str, Any]:
    """
    Search Facebook for posts about each approved tourist spot.
    Stores results in external_reviews with tourist_spot_id set.
    """
    try:
        spots = (
            get_supabase()
            .table("tourist_spots")
            .select("id, name, lgus(name)")
            .eq("approval_status", "approved")
            .limit(20)
            .execute()
            .data
            or []
        )
    except Exception:
        return {"ok": False, "error": "Could not fetch spots", "inserted": 0}

    inserted = 0
    errors: list[str] = []

    for spot in spots:
        spot_id = spot["id"]
        name = spot.get("name", "")
        lgu = (spot.get("lgus") or {}).get("name", "Laguna")
        if not name:
            continue

        query = f"{name} {lgu} Philippines"
        posts = _fb_search(query)

        for post in posts:
            try:
                if _store_post(post, tourist_spot_id=spot_id, event_id=None):
                    inserted += 1
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        time.sleep(0.5)  # Rate limit

    return {"ok": True, "inserted": inserted, "errors": errors}


def scrape_events_social() -> dict[str, Any]:
    """
    Search Facebook for posts about approved events.
    Stores results in external_reviews with event_id set.
    Requires event_id column in external_reviews (run SQL migration).
    """
    try:
        events = (
            get_supabase()
            .table("events")
            .select("id, title, event_status, lgus(name)")
            .eq("approval_status", "approved")
            .in_("event_status", ["finished", "ongoing", "upcoming"])
            .limit(15)
            .execute()
            .data
            or []
        )
    except Exception:
        return {"ok": False, "error": "Could not fetch events", "inserted": 0}

    inserted = 0
    errors: list[str] = []

    for event in events:
        event_id = event["id"]
        title = event.get("title", "")
        lgu = (event.get("lgus") or {}).get("name", "Laguna")
        if not title:
            continue

        query = f"{title} {lgu} Philippines"
        posts = _fb_search(query)

        for post in posts:
            try:
                if _store_post(post, tourist_spot_id=None, event_id=event_id):
                    inserted += 1
            except Exception as exc:
                errors.append(f"{title}: {exc}")

        time.sleep(0.5)

    return {"ok": True, "inserted": inserted, "errors": errors}


def scrape_social_all() -> dict[str, Any]:
    """Run both spot and event social media scraping in sequence."""
    r1 = scrape_spots_social()
    r2 = scrape_events_social()
    return {
        "ok": True,
        "spots_inserted": r1.get("inserted", 0),
        "events_inserted": r2.get("inserted", 0),
        "inserted": r1.get("inserted", 0) + r2.get("inserted", 0),
        "errors": r1.get("errors", []) + r2.get("errors", []),
    }
