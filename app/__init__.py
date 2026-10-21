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
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import get_config

# `db` is the shared SQLAlchemy object. Models and routes import it from here:
#   from app import db
db = SQLAlchemy()

# Flask-Login keeps the logged-in user in the session ("current_user").
login_manager = LoginManager()
# Flask-WTF checks the CSRF token hidden in every HTML form.
csrf = CSRFProtect()


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

    # Customer login (Flask-Login) + CSRF protection on every form.
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"          # where ?next= redirects
    login_manager.login_message_category = "info"    # flash style

    # Secure session cookie defaults (protects the login session).
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    # Secure cookies only make sense over HTTPS (production).
    if not app.debug:
        app.config.setdefault("SESSION_COOKIE_SECURE", True)

    # Money formatting filter, available in every template.
    app.jinja_env.filters["inr"] = inr

    # Register routes. Each Blueprint is a group of related pages.
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Admin panel (Step 5) — all /admin routes, admin-only.
    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    # Custom CLI commands (flask make-admin <email>).
    from app.cli import register_commands
    register_commands(app)

    # Custom error pages (clean messages instead of Flask's defaults).
    from flask import render_template

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    # Create database tables on first run so the app works even before seed.py.
    # (seed.py also calls create_all — harmless to do it twice.)
    with app.app_context():
        db.create_all()
        _migrate_user_columns()
        _migrate_step5_columns()

    return app


def _migrate_user_columns():
    """Add the customer-login columns to an existing users table if missing.

    db.create_all() only creates *missing tables*, never missing columns, so a
    database made in Step 2 needs this one-time ALTER. Safe to run repeatedly;
    existing rows (the admin account) are left untouched.
    """
    from sqlalchemy import inspect

    columns = {c["name"] for c in inspect(db.engine).get_columns("users")}
    if "name" not in columns:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN name VARCHAR(120)"))
    if "phone" not in columns:
        db.session.execute(db.text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
    db.session.commit()


def _migrate_step5_columns():
    """Add Step 5 admin columns to existing tables if missing.

    - products.is_active      — hide a product from the store without deleting it
    - product_images.public_id — Cloudinary id so we can delete/replace uploads

    Safe to run repeatedly; existing rows are untouched.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)

    product_cols = {c["name"] for c in inspector.get_columns("products")}
    if "is_active" not in product_cols:
        # Default TRUE so every existing product stays visible after the upgrade.
        db.session.execute(db.text(
            "ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
        ))

    image_cols = {c["name"] for c in inspector.get_columns("product_images")}
    if "public_id" not in image_cols:
        db.session.execute(db.text(
            "ALTER TABLE product_images ADD COLUMN public_id VARCHAR(300)"
        ))

    db.session.commit()
