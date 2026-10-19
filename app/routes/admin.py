"""
Admin blueprint — the owner-only panel.

Every /admin route lives in this ONE blueprint and is protected by the
@admin_required decorator:

    not logged in        -> redirect to /login (Flask-Login does this)
    logged in, not admin -> 403 Forbidden page

Routes (this step):
    /admin               Dashboard with store stats

Routes (later steps of Step 5):
    /admin/categories    Categories CRUD
    /admin/products      Products CRUD
    /admin/orders        Orders list + detail
"""

from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import Category, Order, Product, ProductVariant

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Order statuses shown on the dashboard (same list Feature 3 will use).
ORDER_STATUSES = ["New", "Confirmed", "Shipped", "Delivered", "Cancelled"]

# A variant with this much stock or less counts as "low stock" on the dashboard.
LOW_STOCK_LEVEL = 3


def admin_required(f):
    """Protect a route: must be logged in AND is_admin.

    - Anonymous users are sent to /login by @login_required (with ?next=).
    - Logged-in customers get a 403 page — they are real users, just not admins.
    """

    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return wrapped


# ---------- dashboard ----------

@admin_bp.route("/", strict_slashes=False)
@admin_required
def dashboard():
    """One-screen summary of the store: counts, sales, low stock, recent orders."""

    total_products = Product.query.count()
    total_categories = Category.query.count()
    total_orders = Order.query.count()

    # Orders grouped by status -> {"New": 3, "Confirmed": 1, ...}
    # Every known status shows up even with a count of 0.
    status_rows = (
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    status_counts = {status: 0 for status in ORDER_STATUSES}
    for status, count in status_rows:
        status_counts[status] = count

    # "Today" in UTC — created_at stores UTC, same as everywhere else in the app.
    today = datetime.now(timezone.utc).date()
    todays_orders = (
        db.session.query(func.count(Order.id))
        .filter(func.date(Order.created_at) == today)
        .scalar()
        or 0
    )

    # Total sales = sum of totals of every order that was NOT cancelled.
    total_sales = (
        db.session.query(func.coalesce(func.sum(Order.total), 0))
        .filter(Order.status != "Cancelled")
        .scalar()
        or 0
    )

    # Low-stock variants: stock <= 3. Ordered lowest first so the worst
    # offenders are on top.
    low_stock = (
        ProductVariant.query.options(db.joinedload(ProductVariant.product))
        .filter(ProductVariant.stock <= LOW_STOCK_LEVEL)
        .order_by(ProductVariant.stock.asc())
        .limit(15)
        .all()
    )

    # 10 most recent orders (newest first).
    recent_orders = (
        Order.query.order_by(Order.created_at.desc(), Order.id.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        title="Admin — Dashboard",
        total_products=total_products,
        total_categories=total_categories,
        total_orders=total_orders,
        status_counts=status_counts,
        todays_orders=todays_orders,
        total_sales=total_sales,
        low_stock=low_stock,
        recent_orders=recent_orders,
        low_stock_level=LOW_STOCK_LEVEL,
    )
