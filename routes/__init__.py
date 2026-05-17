from .auth import auth_bp
from .dashboard import dashboard_bp
from .site import events_bp, itinerary_bp, lgu_bp, profile_bp, public_bp, spots_bp


def register_blueprints(app):
    app.register_blueprint(public_bp)
    app.register_blueprint(spots_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(lgu_bp)
    app.register_blueprint(itinerary_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
