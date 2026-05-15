import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from routes import register_blueprints
from services.tourist_auth import get_current_tourist
from utils.jinja_helpers import register_template_filters

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

    register_template_filters(app)
    register_blueprints(app)

    @app.context_processor
    def inject_tourist():
        return {"current_tourist": get_current_tourist()}

    return app
