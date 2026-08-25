import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

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

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_auth_context():
        tourist = get_current_tourist()
        dashboard_user = get_current_dashboard_user()

        # Fetched fresh every request rather than cached in the session: a
        # session-cached value that was ever written during a failed lookup
        # has no way to self-correct short of the user logging out, which
        # turned one transient DB hiccup into a sticky, hard-to-diagnose bug.
        # get_tourist_profile() already retries against a fresh Supabase
        # client internally, so this stays cheap and resilient without the
        # caching layer's failure mode.
        tourist_profile_image = None
        if tourist:
            try:
                from services.profiles import get_tourist_profile
                from utils.jinja_helpers import normalize_image_url as _nu

                p = get_tourist_profile(tourist["id"])
                tourist_profile_image = _nu(p.get("profile_image") if p else None)
            except Exception:
                tourist_profile_image = None

        return {
            "current_tourist": tourist,
            "current_dashboard_user": dashboard_user,
            "dashboard_nav_items": get_nav_items(dashboard_user["role"])
            if dashboard_user
            else [],
            "tourist_profile_image": tourist_profile_image,
        }

    return app
