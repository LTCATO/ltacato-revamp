"""Public-facing routes: home, spots, events."""

from routes.public.events import events_bp
from routes.public.pages import public_bp
from routes.public.spots import spots_bp

__all__ = ["public_bp", "spots_bp", "events_bp"]
