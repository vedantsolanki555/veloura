"""
Main blueprint: public pages of the store.

Phase 2 routes:
    /                     Home — hero, featured, categories, new arrivals, why section
    /shop                 All products; ?q= search, ?min/?max= price, ?sort=
    /shop/<slug>          One category (men, women, kids, accessories)
    /product/<id>         Product detail placeholder (real page in Phase 3)
"""

from flask import Blueprint, render_template, request

from app.models import Category, Product

main_bp = Blueprint("main", __name__)


# ---------- helpers ----------

def _first_image_url(product):
    """Return the product's first image URL, or a placeholder if none exists."""
    if product.images:
        return product.images[0].image_url
    return "https://placehold.co/600x800?text=Veloura"


# ---------- pages ----------

@main_bp.route("/")
def home():
    """Home page: hero, featured products, category tiles, new arrivals."""
    # Products need their category + images for the cards.
    # joinedload = fetch category/images in the same query (fewer DB round-trips).
    from sqlalchemy.orm import joinedload

    featured = (
        Product.query.options(joinedload(Product.category), joinedload(Product.images))
        .filter_by(is_featured=True)
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )

    # New Arrivals: latest 8 products by created_at.
    new_arrivals = (
        Product.query.options(joinedload(Product.category), joinedload(Product.images))
        .filter_by(is_new=True)
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )

    categories = Category.query.order_by(Category.name).all()

    return render_template(
        "home.html",
        featured=featured,
        new_arrivals=new_arrivals,
        categories=categories,
    )


@main_bp.route("/shop")
def shop():
    """Shop page: all products with search / price filter / sort."""
    context = _query_products(category_slug=None)
    context["all_categories"] = Category.query.order_by(Category.name).all()
    context["active_category"] = None
    return render_template("shop.html", **context)


@main_bp.route("/shop/<slug>")
def shop_category(slug):
    """Shop page filtered to one category, e.g. /shop/men."""
    category = Category.query.filter_by(slug=slug).first_or_404()

    context = _query_products(category_slug=slug)
    context["all_categories"] = Category.query.order_by(Category.name).all()
    context["active_category"] = slug
    return render_template("shop.html", **context)


@main_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    """Product detail — placeholder only; real page is built in Phase 3."""
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product)


# ---------- internals ----------

def _query_products(category_slug, limit=60):
    """Fetch products with category filter, search, price filter and sort.

    Reads these query-string params (all optional):
        q     — search text (name or description)
        min   — minimum price
        max   — maximum price
        sort  — newest (default) | price_asc | price_desc

    Returns a dict ready to be passed into render_template.
    """
    from sqlalchemy.orm import joinedload

    query = Product.query.options(
        joinedload(Product.category), joinedload(Product.images)
    )

    # --- category filter ---
    if category_slug:
        query = query.join(Product.category).filter(Category.slug == category_slug)
        page_title = category_slug.replace("-", " ").title()
    else:
        page_title = "Shop"

    # --- text search (case-insensitive) ---
    search_query = request.args.get("q", "").strip()
    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            db_or(Product.name.ilike(pattern), Product.description.ilike(pattern))
        )
        page_title = "Search"

    # --- price filter (works together with category + search) ---
    # Blank input = no limit on that side.
    min_raw = request.args.get("min", "").strip()
    max_raw = request.args.get("max", "").strip()
    min_price = _to_number(min_raw)
    max_price = _to_number(max_raw)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # --- sort ---
    sort = request.args.get("sort", "newest")
    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    else:
        # default = newest
        sort = "newest"
        query = query.order_by(Product.created_at.desc())

    products = query.limit(limit).all()

    return {
        "products": products,
        "page_title": page_title,
        "search_query": search_query,
        "min_price": min_raw,   # keep raw strings so the inputs remember values
        "max_price": max_raw,
        "sort": sort,
    }


def _to_number(raw):
    """Convert a form string to float. Returns None if blank or invalid."""
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def db_or(*conditions):
    """Tiny helper: SQL OR for multiple ilike conditions."""
    from sqlalchemy import or_
    return or_(*conditions)
