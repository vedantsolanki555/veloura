"""
App factory for Veloura.

"App factory" means: a function that builds and returns a configured Flask
app. This pattern keeps the app object clean and makes testing easier later.

What happens here:
1. Create the Flask app.
2. Apply settings from config.py.
3. Initialise the database (db).
4. Register URL blueprints (routes).
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import get_config

# `db` is the shared SQLAlchemy object. Models and routes import it from here:
#   from app import db
db = SQLAlchemy()


def inr(value):
    """Indian money format for templates: {{ product.price | inr }} -> ₹2,499.

    Uses Indian digit grouping (2,499 / 1,24,999) and never shows decimals.
    """
    try:
        amount = int(round(float(value)))
    except (TypeError, ValueError):
        return value  # not a number — show it unchanged instead of crashing

    digits = str(abs(amount))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:          # group the remaining digits in pairs
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])

    sign = "-" if amount < 0 else ""
    return f"{sign}₹{digits}"


def create_app():
    """Create and configure the Veloura Flask application."""

    app = Flask(__name__)

    # Apply configuration (SECRET_KEY, DATABASE_URL, etc.)
    app.config.from_object(get_config())

    # Connect the database to this app.
    db.init_app(app)

    # Money formatting filter, available in every template.
    app.jinja_env.filters["inr"] = inr

    # Register routes. Each Blueprint is a group of related pages.
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    # Custom 404 page (clean message instead of Flask's default error page).
    from flask import render_template

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    # Create database tables on first run so the app works even before seed.py.
    # (seed.py also calls create_all — harmless to do it twice.)
    with app.app_context():
        db.create_all()

    return app
