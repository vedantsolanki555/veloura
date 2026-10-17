"""
Main blueprint: public pages of the store.

Routes:
    /                     Home — hero, featured, categories, new arrivals, why section
    /shop                 All products; ?q= search, ?min/?max= price, ?sort=
    /shop/<slug>          One category (men, women, kids, accessories)
    /product/<id>         Product detail — gallery, variants, WhatsApp order
"""

import os

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

    # Real model / category photos for the home page (from app/images.py).
    from app.images import CATEGORY_IMAGES, MODEL_IMAGES

    return render_template(
        "home.html",
        featured=featured,
        new_arrivals=new_arrivals,
        categories=categories,
        category_images=CATEGORY_IMAGES,
        model_images=MODEL_IMAGES,
    )


@main_bp.route("/shop")
def shop():
    """Shop page: all products with search / price filter / sort."""
    context = _query_products(category_slug=None)
    context["all_categories"] = Category.query.order_by(Category.name).all()
    context["active_category"] = None
    context["meta_description"] = _shop_meta(context)
    return render_template("shop.html", **context)


@main_bp.route("/shop/<slug>")
def shop_category(slug):
    """Shop page filtered to one category, e.g. /shop/men."""
    category = Category.query.filter_by(slug=slug).first_or_404()

    context = _query_products(category_slug=slug)
    context["all_categories"] = Category.query.order_by(Category.name).all()
    context["active_category"] = slug
    context["category_obj"] = category
    context["meta_description"] = _shop_meta(context)
    return render_template("shop.html", **context)


@main_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    """Product detail page: photos, sizes, quantity, related products."""
    from sqlalchemy.orm import joinedload

    product = (
        Product.query.options(
            joinedload(Product.category),
            joinedload(Product.images),
            joinedload(Product.variants),
        )
        .filter_by(id=product_id)
        .first_or_404()
    )

    # Total stock across all size/colour variants.
    total_stock = sum(v.stock for v in product.variants)

    # Unique sizes for the size selector (e.g. S, M, L, XL or Free).
    sizes = sorted({v.size for v in product.variants})

    # Unique colours, in the order they appear (for the colour swatches).
    colours = list(dict.fromkeys(v.colour for v in product.variants))

    # Every variant as plain data — the page uses it to decide which
    # size + colour combination is available and how much stock is left.
    variants_json = [
        {"id": v.id, "size": v.size, "colour": v.colour, "stock": v.stock}
        for v in product.variants
    ]

    # Sizes / colours that have at least one option in stock — the
    # template renders these as enabled buttons even before JS loads.
    sizes_in_stock = {v.size for v in product.variants if v.stock > 0}
    colours_in_stock = {v.colour for v in product.variants if v.stock > 0}

    # Description for search engines: name + the start of the description.
    short_desc = (product.description or "").strip().split(".")[0][:120]
    meta_description = f"{product.name} — {short_desc}" if short_desc else (
        f"{product.name} at Veloura. Free delivery and cash on delivery."
    )

    # "You may also like": 4 other products from the same category.
    related = (
        Product.query.options(
            joinedload(Product.category), joinedload(Product.images)
        )
        .filter(
            Product.category_id == product.category_id,
            Product.id != product.id,
        )
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )

    return render_template(
        "product_detail.html",
        product=product,
        total_stock=total_stock,
        sizes=sizes,
        colours=colours,
        sizes_in_stock=sizes_in_stock,
        colours_in_stock=colours_in_stock,
        variants_json=variants_json,
        whatsapp_number=_whatsapp_number(),
        meta_description=meta_description,
        related=related,
    )


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

    # Effective price = discounted price when there is one, else full price.
    # Used for BOTH the price filter and the sort, so the page always
    # matches the price actually shown on the card.
    from sqlalchemy import func
    effective_price = func.coalesce(Product.discount_price, Product.price)

    # --- price filter (works together with category + search) ---
    # Blank input = no limit on that side.
    min_raw = request.args.get("min", "").strip()
    max_raw = request.args.get("max", "").strip()
    min_price = _to_number(min_raw)
    max_price = _to_number(max_raw)
    if min_price is not None:
        query = query.filter(effective_price >= min_price)
    if max_price is not None:
        query = query.filter(effective_price <= max_price)

    # --- sort ---
    sort = request.args.get("sort", "newest")
    if sort == "price_asc":
        query = query.order_by(effective_price.asc())
    elif sort == "price_desc":
        query = query.order_by(effective_price.desc())
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


def _whatsapp_number():
    """WHATSAPP_NUMBER from the environment as digits only, e.g. 919876543210.

    The wa.me link format is country-code + number with no +, spaces or dashes,
    so anything that is not a digit is stripped.
    """
    raw = os.environ.get("WHATSAPP_NUMBER", "") or ""
    return "".join(ch for ch in raw if ch.isdigit())


def _shop_meta(context):
    """Per-page meta description for the Shop and category pages."""
    count = len(context["products"])
    query = context.get("search_query") or ""
    if query:
        return (
            f'{count} result{"s" if count != 1 else ""} for "{query}" at Veloura '
            "— premium clothing with free delivery and cash on delivery."
        )
    if context.get("active_category"):
        return (
            f'Buy {context["page_title"]} online at Veloura — {count} premium '
            "pieces, free delivery and cash on delivery."
        )
    return (
        f"Shop {count} premium clothing pieces at Veloura — free delivery, "
        "easy returns and cash on delivery."
    )
