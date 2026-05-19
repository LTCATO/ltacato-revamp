"""
News scraper — Google News RSS (free, no API key).
Scrapes Laguna Province tourism news + per-spot articles.
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

BASE_QUERIES: list[dict] = [
    {"q": "Laguna province Philippines tourism", "cat": "tourism_news"},
    {"q": "DOT Philippines Calabarzon Laguna tourism", "cat": "dot_announcement"},
    {"q": "Laguna tourist spot Philippines destination", "cat": "tourism_news"},
    {"q": "Pagsanjan Falls Los Baños Laguna travel", "cat": "tourism_news"},
    {"q": "Laguna Philippines fiesta festival 2025", "cat": "local_news"},
    {"q": "Laguna Philippines travel blog review", "cat": "tourism_news"},
    {"q": "Laguna heritage cultural tourism Philippines", "cat": "tourism_news"},
    {"q": "eco-tourism Laguna Philippines adventure", "cat": "tourism_news"},
    {"q": "Laguna pilgrim religious tourism Philippines", "cat": "local_news"},
    {"q": "Santa Cruz Pagsanjan Cavinti Nagcarlan tourism", "cat": "local_news"},
]


def _get_spot_names() -> list[str]:
    try:
        rows = (
            get_supabase()
            .table("tourist_spots")
            .select("name")
            .eq("approval_status", "approved")
            .limit(30)
            .execute()
            .data
            or []
        )
        return [r["name"] for r in rows if r.get("name")]
    except Exception:
        return []


def _already_scraped(url: str) -> bool:
    if not url:
        return False
    try:
        return bool(
            get_supabase()
            .table("scraped_news")
            .select("id")
            .eq("source_url", url[:2000])
            .limit(1)
            .execute()
            .data
        )
    except Exception:
        return False


def _title_already_scraped(title: str) -> bool:
    """Deduplicate by the first 60 chars of the title (catches same story, different source)."""
    prefix = title[:60].strip()
    if not prefix:
        return False
    try:
        return bool(
            get_supabase()
            .table("scraped_news")
            .select("id")
            .ilike("title", f"{prefix}%")
            .limit(1)
            .execute()
            .data
        )
    except Exception:
        return False


def _clean_html(raw: str) -> str:
    try:
        return BeautifulSoup(raw, "html.parser").get_text(strip=True)[:800]
    except Exception:
        return (raw or "")[:800]


def _parse_date(entry: dict) -> str | None:
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            return datetime.utcfromtimestamp(calendar.timegm(parsed)).isoformat()
        except Exception:
            pass
    return None


def _source_name(entry: dict) -> str:
    src = entry.get("source") or {}
    return src.get("title", "Google News") if isinstance(src, dict) else "Google News"


def _fetch_and_insert(query: str, category: str) -> tuple[int, list[str]]:
    url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en-PH&gl=PH&ceid=PH:en"
    inserted = 0
    errors: list[str] = []
    try:
        feed = feedparser.parse(url)
        for entry in (feed.entries or [])[:5]:
            try:
                link = entry.get("link", "")
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                if link and _already_scraped(link):
                    continue
                if _title_already_scraped(title):
                    continue
                summary = _clean_html(entry.get("summary", ""))
                full_text = f"{title}. {summary}"
                sentiment_label, sentiment_score = analyze_sentiment(full_text)
                published = _parse_date(entry)
                get_supabase().table("scraped_news").insert(
                    {
                        "title": title[:500],
                        "summary": summary,
                        "source": _source_name(entry),
                        "source_url": link[:2000] if link else None,
                        "category": category,
                        "sentiment": sentiment_label,
                        "sentiment_score": sentiment_score,
                        "keywords": [],
                        "published_at": published,
                        "scraped_at": datetime.utcnow().isoformat(),
                    }
                ).execute()
                inserted += 1
            except Exception as exc:
                errors.append(f"Entry error ({query[:30]}): {exc}")
    except Exception as exc:
        errors.append(f"Fetch error ({query[:40]}): {exc}")
    return inserted, errors


def scrape_news() -> dict[str, Any]:
    inserted = 0
    errors: list[str] = []
    for cfg in BASE_QUERIES:
        n, e = _fetch_and_insert(cfg["q"], cfg["cat"])
        inserted += n
        errors.extend(e)
        time.sleep(0.4)
    for name in _get_spot_names():
        q = f'"{name}" tourism Laguna Philippines'
        n, e = _fetch_and_insert(q, "tourism_news")
        inserted += n
        errors.extend(e)
        time.sleep(0.3)
    return {"ok": True, "inserted": inserted, "errors": errors}


def get_latest_news(limit: int = 20) -> list[dict]:
    try:
        return (
            get_supabase()
            .table("scraped_news")
            .select(
                "id,title,summary,source,category,sentiment,sentiment_score,source_url,scraped_at"
            )
            .order("scraped_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        return []
