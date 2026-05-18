import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, session

from routes import register_blueprints
from services.dashboard_auth import get_current_dashboard_user, get_nav_items
from services.tourist_auth import get_current_tourist
from utils.jinja_helpers import register_template_filters

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

    register_template_filters(app)
    register_blueprints(app)

    @app.context_processor
    def inject_auth_context():
        tourist = get_current_tourist()
        dashboard_user = get_current_dashboard_user()

        # Load tourist profile image (cached in session to avoid per-request DB calls)
        tourist_profile_image = None
        if tourist:
            cached = session.get("tourist_profile_image")
            if cached is None:
                # First request after login — load from DB
                try:
                    from services.profiles import get_tourist_profile
                    from utils.jinja_helpers import normalize_image_url as _nu

                    p = get_tourist_profile(tourist["id"])
                    img = _nu(p.get("profile_image") if p else None)
                    session["tourist_profile_image"] = img or ""
                except Exception:
                    session["tourist_profile_image"] = ""
            tourist_profile_image = session.get("tourist_profile_image") or None

        return {
            "current_tourist": tourist,
            "current_dashboard_user": dashboard_user,
            "dashboard_nav_items": get_nav_items(dashboard_user["role"])
            if dashboard_user
            else [],
            "tourist_profile_image": tourist_profile_image,
        }

    return app
