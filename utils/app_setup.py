import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from routes import register_blueprints
from services.dashboard_auth import get_current_dashboard_user, get_nav_items
from services.tourist_auth import get_current_tourist
from utils.jinja_helpers import register_template_filters

BASE_DIR = Path(os.getcwd())


def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    secret_key = os.getenv("FLASK_SECRET_KEY")
    if not secret_key:
        raise ValueError("❌ FLASK_SECRET_KEY is not set! Add it to your Vercel env vars.")
    app.config["SECRET_KEY"] = secret_key

    register_template_filters(app)
    register_blueprints(app)

    @app.context_processor
    def inject_auth_context():
        try:
            tourist = get_current_tourist()
            dashboard_user = get_current_dashboard_user()
            return {
                "current_tourist": tourist,
                "current_dashboard_user": dashboard_user,
                "dashboard_nav_items": get_nav_items(dashboard_user["role"])
                if dashboard_user
                else [],
            }
        except Exception as e:
            print(f"[Context Processor Error]: {e}")
            return {
                "current_tourist": None,
                "current_dashboard_user": None,
                "dashboard_nav_items": [],
            }

    return app