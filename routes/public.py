from flask import Blueprint, render_template

from services.citizen_charter import ABOUT_LAGUNA, CHARTER_SECTIONS
from services.governor import GOVERNOR, GOVERNOR_TEASER

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    return render_template("views/public/home.html")


@public_bp.route("/about")
def about():
    return render_template(
        "views/public/about.html",
        about=ABOUT_LAGUNA,
        charter_sections=CHARTER_SECTIONS,
        governor_teaser=GOVERNOR_TEASER,
    )


@public_bp.route("/about/governor")
def governor():
    return render_template("views/public/governor.html", governor=GOVERNOR)
