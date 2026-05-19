"""
Sentiment analysis using TextBlob with Tagalog/Filipino support.
Non-English text (detected via langdetect) is first translated to English
using deep-translator (free Google Translate wrapper, no API key needed),
then analyzed with TextBlob.

Install: pip install textblob langdetect deep-translator
"""

from __future__ import annotations

from typing import Any

from services.supabase_client import get_supabase


def _translate_to_english(text: str) -> str:
    """
    Detect language and translate to English if Filipino/Tagalog or other
    non-English language. Returns original text if translation fails.
    """
    if not text or len(text.strip()) < 3:
        return text
    try:
        from langdetect import LangDetectException, detect  # type: ignore

        try:
            lang = detect(text[:300])
        except Exception:
            return text

        # Only translate if NOT English
        if lang != "en":
            try:
                from deep_translator import GoogleTranslator  # type: ignore

                translated = GoogleTranslator(source="auto", target="en").translate(
                    text[:500]
                )
                return translated if translated else text
            except Exception:
                return text
    except ImportError:
        pass
    return text


def analyze_sentiment(text: str) -> tuple[str, float]:
    """
    Return (label, polarity) for text.
    Supports English and Filipino/Tagalog (auto-translated before analysis).
    label: 'positive' | 'neutral' | 'negative'
    polarity: -1.0 to 1.0
    """
    if not text or not text.strip():
        return "neutral", 0.0

    # Translate to English if needed (handles Tagalog, mixed language, etc.)
    working_text = _translate_to_english(text)

    try:
        from textblob import TextBlob  # type: ignore

        score = round(float(TextBlob(working_text).sentiment.polarity), 4)
    except Exception:
        return "neutral", 0.0

    if score > 0.1:
        return "positive", score
    if score < -0.1:
        return "negative", score
    return "neutral", score


def analyze_all_feedbacks(limit: int = 300, force: bool = False) -> dict[str, Any]:
    """
    Analyze sentiment for feedbacks.
    force=False: only rows where sentiment IS NULL (default)
    force=True:  re-analyze ALL rows (use after adding Tagalog support)
    """
    try:
        q = get_supabase().table("feedbacks").select("id, comments, suggestions")
        if not force:
            q = q.is_("sentiment", "null")
        rows = q.limit(limit).execute().data or []
    except Exception as exc:
        return {"ok": False, "error": str(exc), "updated": 0}

    updated = 0
    for row in rows:
        text = " ".join(
            filter(None, [row.get("comments"), row.get("suggestions")])
        ).strip()
        if not text:
            continue
        label, _ = analyze_sentiment(text)
        try:
            get_supabase().table("feedbacks").update({"sentiment": label}).eq(
                "id", row["id"]
            ).execute()
            updated += 1
        except Exception:
            pass
    return {"ok": True, "updated": updated}


def analyze_all_external_reviews(
    limit: int = 300, force: bool = False
) -> dict[str, Any]:
    """
    Analyze sentiment for external_reviews.
    force=False: only NULL rows | force=True: re-analyze ALL rows
    """
    try:
        q = get_supabase().table("external_reviews").select("id, review_text")
        if not force:
            q = q.is_("sentiment", "null")
        rows = q.limit(limit).execute().data or []
    except Exception as exc:
        return {"ok": False, "error": str(exc), "updated": 0}

    updated = 0
    for row in rows:
        text = (row.get("review_text") or "").strip()
        if not text:
            continue
        label, _ = analyze_sentiment(text)
        try:
            get_supabase().table("external_reviews").update({"sentiment": label}).eq(
                "id", row["id"]
            ).execute()
            updated += 1
        except Exception:
            pass
    return {"ok": True, "updated": updated}


def get_feedback_sentiment_summary(lgu_id: int | None = None) -> dict[str, Any]:
    try:
        rows = (
            get_supabase()
            .table("feedbacks")
            .select("sentiment, rating, tourist_spots(lgu_id)")
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    if lgu_id:
        rows = [
            r for r in rows if (r.get("tourist_spots") or {}).get("lgu_id") == lgu_id
        ]
    total = len(rows)
    positive = sum(1 for r in rows if r.get("sentiment") == "positive")
    negative = sum(1 for r in rows if r.get("sentiment") == "negative")
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


def get_external_review_sentiment_summary() -> dict[str, Any]:
    try:
        rows = (
            get_supabase().table("external_reviews").select("sentiment").execute().data
            or []
        )
    except Exception:
        rows = []
    total = len(rows)
    positive = sum(1 for r in rows if r.get("sentiment") == "positive")
    negative = sum(1 for r in rows if r.get("sentiment") == "negative")
    neutral = total - positive - negative
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "positive_pct": round(positive / total * 100, 1) if total else 0,
        "negative_pct": round(negative / total * 100, 1) if total else 0,
        "neutral_pct": round(neutral / total * 100, 1) if total else 0,
    }


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
    neutral = 0
    for row in rows:
        text = (row.get("comment") or "").strip()
        if not text:
            continue
        rating = row.get("rating") or 0
        if rating >= 4:
            positive += 1
        elif rating <= 2:
            negative += 1
        else:
            neutral += 1
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
