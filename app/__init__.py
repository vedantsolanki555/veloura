"""
App factory for Veloura.

"App factory" means: a function that builds and returns a configured Flask
app. This pattern keeps the app object clean and makes testing easier later.

What happens here (Step 6 Part 4 — production readiness):
1. Create the Flask app and apply settings from config.py.
2. In production: refuse to start without SECRET_KEY, trust Render's proxy
   headers (ProxyFix), redirect http → https, send security headers (CSP etc.),
   log to stdout, and let Flask-Migrate manage the database schema.
3. In development: create missing tables automatically (SQLite).
"""

import logging
import os
import sys

from flask import Flask, Response, redirect, request
from flask_compress import Compress
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import get_config

# `db` is the shared SQLAlchemy object. Models and routes import it from here:
#   from app import db
db = SQLAlchemy()

# Flask-Migrate (Alembic) — versioned database migrations (Step 6 Part 4).
# Create a migration:  flask db migrate -m "what changed"
# Apply on the server: flask db upgrade   (run automatically on Render)
migrate = Migrate()

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

    # Apply configuration (SECRET_KEY, DATABASE_URL, shipping, cookies…).
    app.config.from_object(get_config())

    is_production = app.config.get("ENFORCE_HTTPS", False)  # set by ProductionConfig

    # ---- Production safety checks (fail fast, with a clear message) ----
    if is_production:
        real_secret = os.environ.get("SECRET_KEY", "")
        if not real_secret or real_secret == "dev-only-insecure-secret-key":
            # Without a real key, sessions cannot be trusted — refuse to start.
            # (This is what gunicorn reports as "Worker failed to boot".)
            raise RuntimeError(
                "SECRET_KEY environment variable is required in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set it in the Render dashboard."
            )

    # Connect the database to this app.
    db.init_app(app)
    migrate.init_app(app, db)

    # Customer login (Flask-Login) + CSRF protection on every form.
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"          # where ?next= redirects
    login_manager.login_message_category = "info"    # flash style

    # gzip every text response (HTML/CSS/JS) — browsers handle it automatically.
    Compress(app)

    # Money formatting filter, available in every template.
    app.jinja_env.filters["inr"] = inr

    # ---- Production plumbing: ProxyFix + HTTPS redirect + logging ----
    if is_production and not app.testing:
        # Render sits in front of us: X-Forwarded-Proto/For carry the real
        # protocol + client IP. ProxyFix teaches Werkzeug to trust them
        # (only ONE proxy hop — Render — so this cannot be spoofed).
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

        # Redirect plain http → https (request.is_secure works thanks to
        # ProxyFix above). /healthz is exempt so Render's health check
        # can never loop.
        @app.before_request
        def force_https():
            if not request.is_secure and request.path != "/healthz":
                return redirect(request.url.replace("http://", "https://", 1), code=301)

        # Log to STDOUT — Render shows it in the "Logs" tab. Only levels and
        # messages are logged; form values, passwords and tokens never are.
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Veloura started in production mode.")

    # ---- Health check for Render (Part 5 wires /healthz into render.yaml) ----
    @app.route("/healthz")
    def healthz():
        """Liveness probe: 200 OK with no database or session involvement."""
        return Response("ok", mimetype="text/plain")

    # ---- Security headers on every response (Step 6 Part 4) ----
    # CSP: only our own scripts/styles, Google Fonts CSS + font files,
    # Cloudinary + placehold.co images. No inline scripts (they were all
    # moved to /static/js/*.js in this step). Inline style="" attributes
    # are still allowed ('unsafe-inline' under style-src) — they are
    # first-party and cannot run code.
    _CSP = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data: https://res.cloudinary.com https://placehold.co",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ])

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    # Register routes. Each Blueprint is a group of related pages.
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Admin panel (Step 5) — all /admin routes, admin-only.
    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    # Cart, checkout (COD) and orders — Step 4 Feature 3.
    from app.routes.cart import cart_bp
    app.register_blueprint(cart_bp)

    # Navbar cart badge — available on every page.
    @app.context_processor
    def inject_cart_count():
        from app.cart import cart_count
        return {"cart_count": cart_count()}

    # Custom CLI commands (flask init-db, flask make-admin, flask list-orders).
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

    @app.errorhandler(500)
    def server_error(_error):
        # Gunicorn catches anything unhandled and turns it into a 500 —
        # this page replaces Flask's plain white error screen.
        return render_template("500.html"), 500

    # Static file caching (Step 6 Part 3):
    # - images/fonts/ico change rarely  -> cache 1 year ("far future")
    # - css/js are NOT fingerprinted     -> cache 7 days so a new deploy
    #   shows up within a week (or after Ctrl+F5).
    _FAR_FUTURE = {"jpg", "jpeg", "png", "webp", "svg", "ico", "woff", "woff2"}
    _WEEK = {"css", "js"}

    @app.after_request
    def add_static_cache_headers(response):
        if request.path.startswith("/static/"):
            ext = request.path.rsplit(".", 1)[-1].lower()
            if ext in _FAR_FUTURE:
                response.cache_control.public = True
                response.cache_control.max_age = 60 * 60 * 24 * 365
            elif ext in _WEEK:
                response.cache_control.public = True
                response.cache_control.max_age = 60 * 60 * 24 * 7
        return response

    # ---- Database bootstrap ----
    # Development: create any missing tables + fix old SQLite files, so
    # `python wsgi.py` works right after cloning. Production: tables come
    # from `flask db upgrade` (Render start command) or `flask init-db`
    # (manual) — the app itself never touches the schema at import time,
    # which is what made the old startup fragile on Postgres.
    if not is_production:
        with app.app_context():
            db.create_all()
            _migrate_user_columns()
            _migrate_step5_columns()
            _migrate_step5_orders()

    return app


# ---------------------------------------------------------------------------
# One-time column upgrades for OLD SQLite databases (development only).
# Each function skips gracefully when a table does not exist yet.
# ---------------------------------------------------------------------------

def _table_exists(inspector, name):
    return inspector.has_table(name)


def _migrate_user_columns():
    """Add the customer-login columns to an existing users table if missing.

    db.create_all() only creates *missing tables*, never missing columns, so a
    database made in Step 2 needs this one-time ALTER. Safe to run repeatedly;
    existing rows (the admin account) are left untouched.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    if not _table_exists(inspector, "users"):
        return

    columns = {c["name"] for c in inspector.get_columns("users")}
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

    if _table_exists(inspector, "products"):
        product_cols = {c["name"] for c in inspector.get_columns("products")}
        if "is_active" not in product_cols:
            # Default TRUE so every existing product stays visible after the upgrade.
            db.session.execute(db.text(
                "ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
            ))

    if _table_exists(inspector, "product_images"):
        image_cols = {c["name"] for c in inspector.get_columns("product_images")}
        if "public_id" not in image_cols:
            db.session.execute(db.text(
                "ALTER TABLE product_images ADD COLUMN public_id VARCHAR(300)"
            ))

    db.session.commit()


def _migrate_step5_orders():
    """Add Step 5 Feature 3 (orders admin) columns to an existing database.

    orders:      order_number, email, state, subtotal, shipping,
                 payment_method, admin_note, stock_restored, user_id
    order_items: product_name, size, colour (snapshots)
    order_status_history: brand-new table (db.create_all handles it)

    Also: old rows created before this step have status 'pending' — they are
    renamed to 'New' so the admin status filter sees them. Safe to re-run.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    if not _table_exists(inspector, "orders"):
        return

    # ---- orders ----
    order_cols = {c["name"] for c in inspector.get_columns("orders")}

    # NOT NULL column additions need a default value; existing rows (there
    # are none yet in a fresh store) are backfilled right after.
    if "order_number" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN order_number VARCHAR(20) "
            "NOT NULL DEFAULT ''"
        ))
    if "email" not in order_cols:
        db.session.execute(db.text("ALTER TABLE orders ADD COLUMN email VARCHAR(120)"))
    if "state" not in order_cols:
        db.session.execute(db.text("ALTER TABLE orders ADD COLUMN state VARCHAR(80)"))
    if "subtotal" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN subtotal NUMERIC(10,2) NOT NULL DEFAULT 0"
        ))
    if "shipping" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN shipping NUMERIC(10,2) NOT NULL DEFAULT 0"
        ))
    if "payment_method" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN payment_method VARCHAR(20) "
            "NOT NULL DEFAULT 'COD'"
        ))
    if "admin_note" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN admin_note TEXT NOT NULL DEFAULT ''"
        ))
    if "stock_restored" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN stock_restored BOOLEAN NOT NULL DEFAULT FALSE"
        ))
    if "user_id" not in order_cols:
        db.session.execute(db.text(
            "ALTER TABLE orders ADD COLUMN user_id INTEGER REFERENCES users(id)"
        ))

    # ---- order_items ----
    if _table_exists(inspector, "order_items"):
        item_cols = {c["name"] for c in inspector.get_columns("order_items")}
        if "product_name" not in item_cols:
            db.session.execute(db.text(
                "ALTER TABLE order_items ADD COLUMN product_name VARCHAR(200) "
                "NOT NULL DEFAULT ''"
            ))
        if "size" not in item_cols:
            db.session.execute(db.text(
                "ALTER TABLE order_items ADD COLUMN size VARCHAR(20) NOT NULL DEFAULT ''"
            ))
        if "colour" not in item_cols:
            db.session.execute(db.text(
                "ALTER TABLE order_items ADD COLUMN colour VARCHAR(50) NOT NULL DEFAULT ''"
            ))

    # Old default status was 'pending' — normalise to the new 'New'.
    db.session.execute(db.text(
        "UPDATE orders SET status = 'New' WHERE status = 'pending'"
    ))

    db.session.commit()

    # Backfill order numbers for any legacy row still showing ''.
    from app.models import Order, generate_order_number

    for order in Order.query.filter(
        (Order.order_number == "") | (Order.order_number.is_(None))
    ).all():
        order.order_number = generate_order_number()
    db.session.commit()
