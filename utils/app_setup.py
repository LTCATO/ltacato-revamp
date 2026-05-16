import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

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
        return {
            "current_tourist": tourist,
            "current_dashboard_user": dashboard_user,
            "dashboard_nav_items": get_nav_items(dashboard_user["role"])
            if dashboard_user
            else [],
        }

    return app
