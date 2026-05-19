"""
Online Reviews Scraper — Google News RSS (free, no API key).
Fetches real reviews for approved tourist spots.
Also provides helpers for reading event_feedbacks, spot feedbacks, and insights.
"""

from __future__ import annotations

import calendar
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
from bs4 import BeautifulSoup

from services.scrapers.sentiment_analyzer import analyze_sentiment
from services.supabase_client import get_supabase

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

FALLBACK_QUERIES: list[str] = [
    "Pagsanjan Falls review travel Philippines",
    "Los Baños Laguna resort review",
    "Hidden Valley Springs Laguna review",
    "Laguna Philippines tourist spot review",
    "Nagcarlan Underground Cemetery review visit",
    "Cavinti Laguna waterfall travel experience",
    "Pila Laguna heritage review tourist",
    "Siniloan Majayjay Laguna travel blog",
]

# Session-level cache to avoid re-processing same entries
_session_seen: set[str] = set()


def _get_approved_spots() -> list[dict]:
    try:
        return (
            get_supabase()
            .table("tourist_spots")
            .select("id, name")
            .eq("approval_status", "approved")
            .limit(25)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def _already_scraped(review_text: str) -> bool:
    """Check session cache first, then DB by text prefix."""
    cache_key = review_text[:80]
    if cache_key in _session_seen:
        return True
    try:
        # Use eq on a short prefix stored as reviewer_name (no special chars issue)
        prefix = review_text[:60]
        # Simple approach: check if exact text already exists via reviewer_name+text prefix
        rows = (
            get_supabase()
            .table("external_reviews")
            .select("id")
            .limit(1)
            .execute()
            .data
            or []
        )
        # Don't query by text to avoid ilike special char issues —
        # rely on session cache for dedup within a run
        return False
    except Exception:
        return False


def _clean_html(raw: str) -> str:
    try:
        return BeautifulSoup(raw, "html.parser").get_text(strip=True)[:600]
    except Exception:
        return (raw or "")[:600]


def _parse_date(entry: dict) -> str:
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            return datetime.utcfromtimestamp(calendar.timegm(parsed)).isoformat()
        except Exception:
            pass
    return datetime.utcnow().isoformat()


def _source_name(entry: dict) -> str:
    src = entry.get("source") or {}
    name = src.get("title", "Google News") if isinstance(src, dict) else "Google News"
    return name[:95]  # Stay within varchar(100) limit


def _fetch_reviews_for_query(query: str, spot_id: int | None) -> tuple[int, list[str]]:
    feed_url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en-PH&gl=PH&ceid=PH:en"
    inserted = 0
    errors: list[str] = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in (feed.entries or [])[:3]:
            try:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                summary = _clean_html(entry.get("summary", ""))
                review_text = f"{title}. {summary}".strip()

                if len(review_text) < 40:
                    continue

                # Session-level dedup
                cache_key = review_text[:80]
                if cache_key in _session_seen:
                    continue
                _session_seen.add(cache_key)

                source = _source_name(entry)
                sentiment_label, _ = analyze_sentiment(review_text)

                get_supabase().table("external_reviews").insert(
                    {
                        "tourist_spot_id": spot_id,
                        "source": source,  # max 95 chars, safe for varchar(100)
                        "reviewer_name": source,  # max 95 chars
                        "review_text": review_text[:2000],
                        "sentiment": sentiment_label,
                        "review_date": _parse_date(entry),
                        "scraped_at": datetime.utcnow().isoformat(),
                    }
                ).execute()
                inserted += 1

            except Exception as exc:
                errors.append(f"Entry ({query[:30]}): {exc}")
    except Exception as exc:
        errors.append(f"Fetch ({query[:40]}): {exc}")
    return inserted, errors


def scrape_online_reviews() -> dict[str, Any]:
    """Scrape real online reviews for all approved tourist spots."""
    global _session_seen
    _session_seen = set()  # Reset session cache each run

    spots = _get_approved_spots()
    inserted = 0
    errors: list[str] = []

    for spot in spots:
        name = spot.get("name", "")
        if not name:
            continue
        n, e = _fetch_reviews_for_query(
            f'"{name}" review travel Philippines', spot.get("id")
        )
        inserted += n
        errors.extend(e)
        time.sleep(0.4)

    for query in FALLBACK_QUERIES:
        n, e = _fetch_reviews_for_query(query, None)
        inserted += n
        errors.extend(e)
        time.sleep(0.3)

    return {"ok": True, "inserted": inserted, "errors": errors}


# ── Feedbacks for Decision Support display ────────────────────────────────


def get_event_feedbacks_for_display(limit: int = 60) -> list[dict]:
    try:
        return (
            get_supabase()
            .table("event_feedbacks")
            .select(
                "id, event_id, rating, comment, created_at, "
                "events(id, title, lgu_id, lgus(id, name))"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def get_spot_feedbacks_for_display(limit: int = 60) -> list[dict]:
    try:
        return (
            get_supabase()
            .table("feedbacks")
            .select(
                "id, rating, comments, suggestions, sentiment, source, "
                "created_at, guest_name, tourist_spots(id, name, lgus(id, name))"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def get_online_reviews_for_display(limit: int = 60) -> list[dict]:
    try:
        return (
            get_supabase()
            .table("external_reviews")
            .select(
                "id, source, reviewer_name, review_text, sentiment, "
                "review_date, scraped_at, tourist_spots(id, name, lgus(id, name))"
            )
            .order("scraped_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def get_event_feedback_sentiment() -> dict[str, Any]:
    try:
        rows = (
            get_supabase()
            .table("event_feedbacks")
            .select("comment, rating")
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    total = len(rows)
    positive = 0
    negative = 0
    for row in rows:
        text = (row.get("comment") or "").strip()
        if text:
            label, _ = analyze_sentiment(text)
            if label == "positive":
                positive += 1
            elif label == "negative":
                negative += 1
    neutral = total - positive - negative
    ratings = [r["rating"] for r in rows if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "positive_pct": round(positive / total * 100, 1) if total else 0,
        "negative_pct": round(negative / total * 100, 1) if total else 0,
        "neutral_pct": round(neutral / total * 100, 1) if total else 0,
        "avg_rating": avg_rating,
    }


def scrape_event_news() -> dict[str, Any]:
    """
    Search Google News for coverage of approved events (finished, ongoing, upcoming).
    Stores results in scraped_news with category='event_news' and
    keywords=[{"event_id": X, "event_title": "..."}] for linking back to the event.

    This lets the insights engine combine internal event_feedbacks with
    real-world online coverage of the same event.
    """
    from urllib.parse import quote_plus as _qp

    try:
        events = (
            get_supabase()
            .table("events")
            .select("id, title, event_status, lgus(name)")
            .eq("approval_status", "approved")
            .in_("event_status", ["finished", "ongoing", "upcoming"])
            .limit(20)
            .execute()
            .data
            or []
        )
    except Exception:
        return {"ok": True, "inserted": 0, "errors": ["Could not fetch events from DB"]}

    inserted = 0
    errors: list[str] = []

    for event in events:
        event_id = event.get("id")
        title = (event.get("title") or "").strip()
        lgu_name = (event.get("lgus") or {}).get("name", "Laguna")
        if not title:
            continue

        query = f'"{title}" {lgu_name} Philippines'
        feed_url = f"{GOOGLE_NEWS_RSS}?q={_qp(query)}&hl=en-PH&gl=PH&ceid=PH:en"

        try:
            import feedparser as _fp

            feed = _fp.parse(feed_url)

            for entry in (feed.entries or [])[:3]:
                try:
                    e_title = (entry.get("title") or "").strip()
                    e_link = entry.get("link", "")
                    if not e_title:
                        continue

                    # Skip if already stored by URL
                    if e_link:
                        existing = (
                            get_supabase()
                            .table("scraped_news")
                            .select("id")
                            .eq("source_url", e_link[:2000])
                            .limit(1)
                            .execute()
                            .data
                        )
                        if existing:
                            continue

                    summary = _clean_html(entry.get("summary", ""))
                    full_text = f"{e_title}. {summary}"

                    from services.scrapers.sentiment_analyzer import (
                        analyze_sentiment as _sa,
                    )

                    sentiment_label, sentiment_score = _sa(full_text)

                    published = _parse_date(entry)
                    src = _source_name(entry)

                    get_supabase().table("scraped_news").insert(
                        {
                            "title": e_title[:500],
                            "summary": summary,
                            "source": src,
                            "source_url": e_link[:2000] if e_link else None,
                            "category": "event_news",
                            "sentiment": sentiment_label,
                            "sentiment_score": sentiment_score,
                            "keywords": [{"event_id": event_id, "event_title": title}],
                            "published_at": published,
                            "scraped_at": datetime.utcnow().isoformat(),
                        }
                    ).execute()
                    inserted += 1

                except Exception as exc:
                    errors.append(f"Event entry ({title[:30]}): {exc}")

            time.sleep(0.4)

        except Exception as exc:
            errors.append(f"Event news fetch ({title[:30]}): {exc}")

    return {"ok": True, "inserted": inserted, "errors": errors}
