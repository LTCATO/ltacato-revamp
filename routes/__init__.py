from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.public import events_bp, public_bp, spots_bp


def register_blueprints(app):
    app.register_blueprint(public_bp)
    app.register_blueprint(spots_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
