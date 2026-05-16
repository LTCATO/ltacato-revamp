"""Dashboard routes package."""

from routes.dashboard.blueprint import dashboard_bp

from routes.dashboard import actions, auth, pages  # noqa: E402, F401

__all__ = ["dashboard_bp"]
