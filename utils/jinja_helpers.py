import re
from typing import Any


def normalize_image_url(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    cleaned = str(url).strip().rstrip("?").replace("//storage", "/storage")
    return cleaned


def ensure_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def list_item_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("text") or item.get("title") or item.get("step") or str(item)
    return str(item)


def category_label(category: str | None) -> str:
    if not category:
        return "Destination"
    return category.replace("_", " ").title()


def event_category_label(category: str | None) -> str:
    labels = {
        "cultural": "Cultural",
        "food": "Food & Drink",
        "adventure": "Adventure",
        "arts": "Arts & Trade",
        "trade": "Trade",
        "festival": "Festival",
    }
    return labels.get((category or "").lower(), category_label(category))


def event_category_icon(category: str | None) -> str:
    icons = {
        "cultural": "ph-theater",
        "food": "ph-bowl-food",
        "adventure": "ph-tree",
        "arts": "ph-palette",
        "trade": "ph-storefront",
        "festival": "ph-confetti",
    }
    return icons.get((category or "").lower(), "ph-calendar-star")


def category_badge_class(category: str | None) -> str:
    mapping = {
        "nature": "spot-badge--nature",
        "resort": "spot-badge--resort",
        "heritage": "spot-badge--heritage",
        "waterfall": "spot-badge--waterfall",
        "religious": "spot-badge--religious",
        "pilgrimage": "spot-badge--pilgrimage",
    }
    return mapping.get((category or "").lower(), "spot-badge--default")


def truncate_text(text: str | None, length: int = 160) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= length:
        return text
    return text[: length - 3].rstrip() + "..."


def stars_display(rating: float | int | None) -> list[str]:
    value = float(rating or 0)
    stars = []
    for i in range(1, 6):
        if value >= i:
            stars.append("full")
        elif value >= i - 0.5:
            stars.append("half")
        else:
            stars.append("empty")
    return stars


def register_template_filters(app) -> None:
    """Register all Jinja filters on the Flask app."""
    app.jinja_env.filters.update(
        {
            "normalize_image_url": normalize_image_url,
            "category_label": category_label,
            "category_badge_class": category_badge_class,
            "ensure_list": ensure_list,
            "list_item_text": list_item_text,
            "truncate_text": truncate_text,
            "stars_display": stars_display,
            "event_category_label": event_category_label,
            "event_category_icon": event_category_icon,
        }
    )
