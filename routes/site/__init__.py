"""Public-facing routes: home, spots, events."""

from routes.site.events import events_bp
from routes.site.pages import public_bp
from routes.site.spots import spots_bp

__all__ = ["public_bp", "spots_bp", "events_bp"]
