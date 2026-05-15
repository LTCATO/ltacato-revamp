from routes.auth import auth_bp
from routes.events import events_bp
from routes.public import public_bp
from routes.spots import spots_bp


def register_blueprints(app):
    app.register_blueprint(public_bp)
    app.register_blueprint(spots_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(auth_bp)
