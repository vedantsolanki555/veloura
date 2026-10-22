"""
Main blueprint: public pages of the store.

Routes:
    /                     Home — hero, featured, categories, new arrivals, why section
    /shop                 All products; ?q= search, ?min/?max= price, ?sort=,
                          ?size=, ?colour=, ?page= (12 per page)
    /shop/<slug>          One category (men, women, kids, accessories)
    /product/<id>         Product detail — gallery, variants, WhatsApp order
"""

import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask import Response
from flask_wtf import FlaskForm
from sqlalchemy.orm import joinedload, selectinload
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app import db
from app.models import Category, ContactMessage, Product, ProductVariant
from app.ratelimit import is_limited, record_failure

main_bp = Blueprint("main", __name__)

# Shop page shows 12 products at a time (pagination).
PER_PAGE = 12

# Preferred display order for common sizes; unknown sizes go last (alphabetical).
_SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "Free"]


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
    # Products need their category + images + variants for the cards
    # (variants tell the card if the product is out of stock).
    # selectinload = ONE extra query for all rows, never one per product.
    featured = (
        Product.query.options(
            joinedload(Product.category),
            selectinload(Product.images),
            selectinload(Product.variants),
        )
        .filter_by(is_featured=True, is_active=True)
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )

    # New Arrivals: latest 8 products by created_at.
    new_arrivals = (
        Product.query.options(
            joinedload(Product.category),
            selectinload(Product.images),
            selectinload(Product.variants),
        )
        .filter_by(is_new=True, is_active=True)
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
    # Use the real category name ("Men", "Accessories") for the <title>.
    context["page_title"] = category.name
    context["meta_description"] = _shop_meta(context)
    return render_template("shop.html", **context)


@main_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    """Product detail page: photos, sizes, quantity, related products."""
    product = (
        Product.query.options(
            joinedload(Product.category),
            joinedload(Product.images),
            joinedload(Product.variants),
        )
        .filter_by(id=product_id, is_active=True)
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

    # Absolute URL of the main photo — used for Open Graph + Product JSON-LD.
    _main_image = product.images[0].image_url if product.images else "/static/img/home/hero-women.jpg"
    if _main_image.startswith("/"):   # local file → make it absolute
        og_image_url = request.url_root.rstrip("/") + _main_image
    else:
        og_image_url = _main_image    # already a Cloudinary https URL

    # "You may also like": 4 other products from the same category.
    related = (
        Product.query.options(
            joinedload(Product.category), joinedload(Product.images)
        )
        .filter(
            Product.category_id == product.category_id,
            Product.id != product.id,
            Product.is_active.is_(True),
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
        og_image_url=og_image_url,
        related=related,
    )


@main_bp.route("/product/<product_slug>")
def product_by_slug(product_slug):
    """Clean slug URL (/product/mens-silk-kurta) → 301 to the id URL.

    Keeps old shared links working and gives search engines ONE canonical
    URL per product (the canonical tag on the product page points to the
    /product/<id> form used everywhere inside the site).
    """
    product = Product.query.filter_by(slug=product_slug, is_active=True).first_or_404()
    return redirect(url_for("main.product_detail", product_id=product.id), code=301)


# ---------- static info pages + contact (Step 6 Part 1) ----------

class ContactForm(FlaskForm):
    """Contact form. Server-side validation — never trust the browser."""

    name = StringField("Your name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone (optional)", validators=[Optional(), Length(max=20)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(min=5, max=2000)])
    submit = SubmitField("Send message")

    def validate_email(self, field):
        """Light email check — same rule as the login/register forms."""
        value = (field.data or "").strip()
        if value.count("@") != 1 or "." not in value.split("@")[-1]:
            from wtforms.validators import ValidationError
            raise ValidationError("Enter a valid email address.")


@main_bp.route("/about")
def about():
    """About page — the Veloura story."""
    return render_template(
        "about.html",
        title="About Us — Veloura",
        meta_description="The story behind Veloura — premium ethnic and contemporary clothing, thoughtfully crafted for every occasion.",
    )


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact page — store details, WhatsApp button, message form."""
    form = ContactForm()
    if form.validate_on_submit():
        # Honeypot: real people never see or fill this field.
        if request.form.get("website"):
            flash("Your message could not be sent. Please try again.", "error")
            return redirect(url_for("main.contact"))

        # Rate limit: 3 messages per IP every 15 minutes (spam protection,
        # shared with /login via app/ratelimit.py).
        rate_key = f"contact|{request.remote_addr}"
        if is_limited(rate_key, max_attempts=3, window=15 * 60):
            flash("Too many messages sent. Please try again in 15 minutes.", "error")
            return redirect(url_for("main.contact"))
        record_failure(rate_key, window=15 * 60)

        db.session.add(
            ContactMessage(
                name=form.name.data.strip(),
                email=form.email.data.strip().lower(),
                phone=("".join(ch for ch in (form.phone.data or "") if ch.isdigit()) or None),
                message=form.message.data.strip(),
            )
        )
        db.session.commit()
        flash("Thank you for reaching out! We will get back to you within 24 hours.", "success")
        return redirect(url_for("main.contact"))

    return render_template(
        "contact.html",
        title="Contact Us — Veloura",
        meta_description="Get in touch with Veloura — WhatsApp, email or send us a message. We reply within 24 hours.",
        form=form,
        whatsapp_number=_whatsapp_number(),
    )


@main_bp.route("/shipping-returns")
def shipping_returns():
    """Shipping & returns policy page."""
    # Live values from .env so the policy page always matches checkout.
    fee = int(current_app.config["SHIPPING_FEE"])
    free_above = int(current_app.config["FREE_SHIPPING_ABOVE"])
    return render_template(
        "shipping_returns.html",
        title="Shipping & Returns — Veloura",
        meta_description=(
            f"Veloura shipping and returns — ₹{fee} shipping below ₹{free_above:,}, "
            "free delivery above that, cash on delivery across India, easy returns."
        ),
        shipping_fee=fee,
        free_shipping_above=free_above,
    )


@main_bp.route("/privacy")
def privacy():
    """Privacy policy page."""
    return render_template(
        "privacy.html",
        title="Privacy Policy — Veloura",
        meta_description="How Veloura collects, uses and protects your personal information.",
    )


@main_bp.route("/terms")
def terms():
    """Terms of service page."""
    return render_template(
        "terms.html",
        title="Terms of Service — Veloura",
        meta_description="The terms and conditions that apply when you shop at Veloura.",
    )


# ---------- SEO: sitemap + robots (Step 6 Part 2) ----------

def _site_url():
    """Absolute site root, from SITE_URL env var (production) or the request.

    Example: "https://veloura.onrender.com" (no trailing slash).
    """
    configured = (os.environ.get("SITE_URL", "") or "").strip()
    if configured:
        return configured.rstrip("/")
    return request.url_root.rstrip("/")


@main_bp.route("/sitemap.xml")
def sitemap():
    """XML sitemap: home, shop, categories, active products, static pages."""
    base = _site_url()

    # (path, lastmod-or-None) — newest content first is not required by Google.
    entries = [
        ("/", None),
        ("/shop", None),
        ("/about", None),
        ("/contact", None),
        ("/shipping-returns", None),
        ("/privacy", None),
        ("/terms", None),
    ]

    for category in Category.query.order_by(Category.id).all():
        entries.append((f"/shop/{category.slug}", None))

    for product in (
        Product.query.filter_by(is_active=True)
        .order_by(Product.created_at.desc())
        .all()
    ):
        lastmod = product.created_at.strftime("%Y-%m-%d") if product.created_at else None
        entries.append((f"/product/{product.id}", lastmod))

    return Response(
        render_template("sitemap.xml", base=base, entries=entries),
        mimetype="application/xml",
    )


@main_bp.route("/robots.txt")
def robots():
    """robots.txt — keep search engines out of admin, cart, checkout, account."""
    sitemap_url = f"{_site_url()}/sitemap.xml"
    body = "\n".join([
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /cart",
        "Disallow: /checkout",
        "Disallow: /account",
        "Disallow: /order",
        "",
        f"Sitemap: {sitemap_url}",
        "",
    ])
    return Response(body, mimetype="text/plain")


# ---------- internals ----------

def _query_products(category_slug):
    """Fetch one page of products (12 per page) with filters + sort.

    Reads these query-string params (all optional):
        q       — search text (name or description)
        min     — minimum price
        max     — maximum price
        sort    — newest (default) | price_asc | price_desc
        size    — keep only products that have this size variant
        colour  — keep only products that have this colour variant
        page    — page number (default 1)

    Returns a dict ready to be passed into render_template.
    """
    from sqlalchemy import func
    from sqlalchemy.orm import selectinload

    # selectinload = images + variants fetched in ONE extra query each
    # (no N+1 — never one query per product).
    query = Product.query.options(
        joinedload(Product.category),
        selectinload(Product.images),
        selectinload(Product.variants),
    ).filter(Product.is_active.is_(True))

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

    # --- size + colour filters ---
    # "Product has a variant with this size/colour" (stock can be 0).
    active_size = request.args.get("size", "").strip()
    active_colour = request.args.get("colour", "").strip()
    if active_size:
        query = query.filter(
            Product.variants.any(ProductVariant.size == active_size)
        )
    if active_colour:
        query = query.filter(
            Product.variants.any(ProductVariant.colour == active_colour)
        )

    # --- sort ---
    sort = request.args.get("sort", "newest")
    if sort == "price_asc":
        query = query.order_by(effective_price.asc(), Product.id.asc())
    elif sort == "price_desc":
        query = query.order_by(effective_price.desc(), Product.id.asc())
    else:
        # default = newest
        sort = "newest"
        query = query.order_by(Product.created_at.desc(), Product.id.desc())

    # --- pagination (12 per page) ---
    page = request.args.get("page", 1, type=int) or 1
    if page < 1:
        page = 1
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    # If someone types ?page=999 on a 3-page list, show the last real page.
    if pagination.pages and page > pagination.pages:
        page = pagination.pages
        pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    products = pagination.items

    return {
        "products": products,
        "pagination": pagination,
        "page_title": page_title,
        "search_query": search_query,
        "min_price": min_raw,   # keep raw strings so the inputs remember values
        "max_price": max_raw,
        "sort": sort,
        "active_size": active_size,
        "active_colour": active_colour,
        "all_sizes": _all_sizes(),
        "all_colours": _all_colours(),
        "range_start": (pagination.page - 1) * PER_PAGE + 1 if products else 0,
        "range_end": (pagination.page - 1) * PER_PAGE + len(products),
        "shop_url": _shop_url,
        "cat_url": _cat_url,
        "page_link": _page_link,
        "page_numbers": _page_numbers(pagination.page, pagination.pages),
    }


def _all_sizes():
    """Every distinct size in the catalogue, in wear-order (S, M, L, ...)."""
    rows = db.session.query(ProductVariant.size).distinct().all()
    values = [r[0] for r in rows]
    return sorted(values, key=lambda s: (_SIZE_ORDER.index(s) if s in _SIZE_ORDER else 99, s))


def _all_colours():
    """Every distinct colour in the catalogue, alphabetical."""
    rows = db.session.query(ProductVariant.colour).distinct().all()
    return sorted(r[0] for r in rows)


def _shop_url(**overrides):
    """Build a /shop (or /shop/<category>) URL from the current query string.

    Every key set to None/"" is dropped; anything else replaces the old value.
    The page number always resets when a filter changes.
    Usage in templates: {{ shop_url(size='M') }}, {{ shop_url(size=None) }}
    """
    args = request.args.to_dict()
    for key, value in overrides.items():
        if value is None or value == "":
            args.pop(key, None)
        else:
            args[key] = value
    args.pop("page", None)  # new filter = back to page 1
    if request.endpoint == "main.shop_category":
        return url_for("main.shop_category", slug=request.view_args["slug"], **args)
    return url_for("main.shop", **args)


def _cat_url(slug):
    """URL for another category, keeping the current search/price/size/colour."""
    args = request.args.to_dict()
    args.pop("page", None)
    return url_for("main.shop_category", slug=slug, **args)


def _page_link(page):
    """URL for a given page number, keeping every active filter in the query."""
    args = request.args.to_dict()
    if page and page > 1:
        args["page"] = page
    else:
        args.pop("page", None)
    if request.endpoint == "main.shop_category":
        return url_for("main.shop_category", slug=request.view_args["slug"], **args)
    return url_for("main.shop", **args)


def _page_numbers(current, total):
    """Page numbers to show in the pager (window around current, ends always)."""
    if total <= 7:
        return list(range(1, total + 1))
    numbers = {1, total, current}
    for offset in (-1, 1):
        neighbour = current + offset
        if 1 < neighbour < total:
            numbers.add(neighbour)
    return sorted(numbers)


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
    # Use the TOTAL match count (not just this page's 12 items).
    pagination = context.get("pagination")
    count = pagination.total if pagination else len(context["products"])
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
