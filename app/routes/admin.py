"""
Admin blueprint — the owner-only panel.

Every /admin route lives in this ONE blueprint and is protected by the
@admin_required decorator:

    not logged in        -> redirect to /login (Flask-Login does this)
    logged in, not admin -> 403 Forbidden page

Routes:
    /admin                      Dashboard with store stats
    /admin/categories           List + add categories
    /admin/categories/<id>/edit Edit one category
    /admin/categories/<id>/delete  Delete (blocked while it has products)
    /admin/products             Product list (search / filter / pagination)
    /admin/products/new         Add product (incl. variants + images)
    /admin/products/<id>/edit   Edit product, variants and images
    /admin/products/<id>/delete Soft or hard delete
    /admin/products/<id>/images Upload more images
    /admin/images/<id>/delete   Delete one image
    /admin/images/<id>/main     Make one image the main (first) image
    /admin/images/<id>/move     Move one image left/right in the gallery
"""

import json
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DecimalField, BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app import db
from app.models import Category, Order, OrderItem, Product, ProductImage, ProductVariant
from app.utils import (
    delete_product_image_file,
    save_product_image,
    slugify,
    unique_slug,
    validate_image_file,
)

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


# ============================================================
# CATEGORIES
# ============================================================

class CategoryForm(FlaskForm):
    """Add / edit a category. Slug is auto-generated from the name."""

    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=80)])
    submit = SubmitField("Save category")

    def validate_name(self, field):
        """Reject a second category with the same name (case-insensitive)."""
        name = field.data.strip()
        query = Category.query.filter(db.func.lower(Category.name) == name.lower())
        # When editing, ignore the row we are editing itself.
        if self._category_id:
            query = query.filter(Category.id != self._category_id)
        if query.first():
            raise ValidationError("A category with this name already exists.")

    # Set by the route before validation so validate_name can skip self.
    _category_id = None


@admin_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    """List all categories with a small add form."""
    form = CategoryForm()

    if form.validate_on_submit():
        name = form.name.data.strip()
        category = Category(name=name, slug=unique_slug(Category, name))
        db.session.add(category)
        db.session.commit()
        flash(f'Category "{category.name}" added.', "success")
        return redirect(url_for("admin.categories"))

    all_categories = Category.query.order_by(Category.name).all()
    # Product count per category for the table (one grouped query, no N+1).
    counts = dict(
        db.session.query(Product.category_id, func.count(Product.id))
        .group_by(Product.category_id)
        .all()
    )
    return render_template(
        "admin/categories.html",
        title="Admin — Categories",
        form=form,
        categories=all_categories,
        product_counts=counts,
    )


@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def category_edit(category_id):
    """Edit one category's name (slug stays as it is — URLs never change)."""
    category = db.session.get(Category, category_id) or abort(404)
    form = CategoryForm(obj=category)
    form._category_id = category.id

    if form.validate_on_submit():
        category.name = form.name.data.strip()
        db.session.commit()
        flash(f'Category renamed to "{category.name}".', "success")
        return redirect(url_for("admin.categories"))

    return render_template(
        "admin/category_edit.html",
        title=f"Admin — Edit {category.name}",
        form=form,
        category=category,
    )


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def category_delete(category_id):
    """Delete a category — only if it has no products left."""
    category = db.session.get(Category, category_id) or abort(404)

    if category.products:
        # Friendly refusal: moving products is safer than losing them.
        flash(
            f'Cannot delete "{category.name}" — it still has '
            f'{len(category.products)} product(s). Move or delete them first.',
            "error",
        )
        return redirect(url_for("admin.categories"))

    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{category.name}" deleted.', "success")
    return redirect(url_for("admin.categories"))


# ============================================================
# PRODUCTS
# ============================================================

class ProductForm(FlaskForm):
    """Add / edit a product (variants and images are handled separately)."""

    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=200)])
    slug = StringField("Slug (URL name)", validators=[Optional(), Length(max=220)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    fabric_care = TextAreaField("Fabric & care", validators=[Optional(), Length(max=5000)])
    price = DecimalField("Price (₹)", validators=[DataRequired(), NumberRange(min=1)])
    discount_price = DecimalField("Discount price (₹)", validators=[Optional(), NumberRange(min=1)])
    is_featured = BooleanField("Featured on home page")
    is_new = BooleanField("New arrival")
    is_active = BooleanField("Active (visible in store)", default=True)
    submit = SubmitField("Save product")

    def __init__(self, *args, **kwargs):
        # `exclude_id` = the product being edited (so its slug/name can stay unique).
        self.exclude_id = kwargs.pop("exclude_id", None)
        super().__init__(*args, **kwargs)
        # Fill the category dropdown from the database.
        self.category_id.choices = [
            (c.id, c.name) for c in Category.query.order_by(Category.name).all()
        ]

    def validate_discount_price(self, field):
        """Discount must be lower than the full price (when both are set)."""
        if field.data is not None and self.price.data is not None:
            if field.data >= self.price.data:
                raise ValidationError("Discount price must be lower than the full price.")

    def validate_slug(self, field):
        """Slug must be unique. Blank = we generate one from the name."""
        raw = (field.data or "").strip()
        if not raw:
            return
        slug = slugify(raw)
        query = Product.query.filter(Product.slug == slug)
        if self.exclude_id:
            query = query.filter(Product.id != self.exclude_id)
        if query.first():
            raise ValidationError("Another product already uses this slug.")


def _parse_variants_from_request():
    """Read the variant rows posted by the form.

    The form sends parallel lists:
        variant_id     — existing DB id, or "" for a brand-new row
        variant_size   — e.g. "M"
        variant_colour — e.g. "Indigo"
        variant_stock  — e.g. "5"

    Returns (variants, errors) where variants is a list of dicts.
    """
    ids = request.form.getlist("variant_id")
    sizes = request.form.getlist("variant_size")
    colours = request.form.getlist("variant_colour")
    stocks = request.form.getlist("variant_stock")

    variants = []
    errors = []
    seen = set()  # (size, colour) pairs already used in this form

    for i, size in enumerate(sizes):
        size = (sizes[i] or "").strip()
        colour = (colours[i] or "").strip() if i < len(colours) else ""
        stock_raw = (stocks[i] or "").strip() if i < len(stocks) else ""
        existing_id = (ids[i] or "").strip() if i < len(ids) else ""

        # Skip a completely empty row (user clicked "add" but filled nothing).
        if not size and not colour and not stock_raw:
            continue

        if not size:
            errors.append(f"Variant {i + 1}: size is required.")
            continue
        if not colour:
            errors.append(f"Variant {i + 1}: colour is required.")
            continue

        try:
            stock = int(stock_raw) if stock_raw else 0
        except ValueError:
            errors.append(f"Variant {i + 1}: stock must be a whole number.")
            continue
        if stock < 0:
            errors.append(f"Variant {i + 1}: stock cannot be negative.")
            continue

        key = (size.lower(), colour.lower())
        if key in seen:
            errors.append(
                f"Variant {i + 1}: duplicate size + colour "
                f"({size} / {colour}) — merge them into one row."
            )
            continue
        seen.add(key)

        variants.append({
            "id": int(existing_id) if existing_id.isdigit() else None,
            "size": size,
            "colour": colour,
            "stock": stock,
        })

    return variants, errors


def _save_variants(product, variants):
    """Apply the parsed variant rows to the product (add / update / remove)."""
    keep_ids = {v["id"] for v in variants if v["id"]}

    # Delete rows the user removed from the form.
    for old in list(product.variants):
        if old.id not in keep_ids:
            db.session.delete(old)

    # Update existing rows, create the new ones.
    for v in variants:
        if v["id"]:
            variant = db.session.get(ProductVariant, v["id"])
            # Safety: never touch a variant that belongs to another product.
            if variant and variant.product_id == product.id:
                variant.size = v["size"]
                variant.colour = v["colour"]
                variant.stock = v["stock"]
        else:
            db.session.add(ProductVariant(
                product=product,
                size=v["size"],
                colour=v["colour"],
                stock=v["stock"],
            ))


def _thumbnail_url(product):
    return product.images[0].image_url if product.images else ""


@admin_bp.route("/products")
@admin_required
def products():
    """Product list: search, category filter, stock filter, 20 per page."""
    page = request.args.get("page", 1, type=int) or 1
    search = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    stock_filter = request.args.get("stock", "").strip()

    query = Product.query.options(
        db.joinedload(Product.category),
        db.selectinload(Product.images),
        db.selectinload(Product.variants),
    )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            db.or_(Product.name.ilike(pattern), Product.slug.ilike(pattern))
        )

    if category_filter.isdigit():
        query = query.filter(Product.category_id == int(category_filter))

    # Stock filter works on TOTAL stock (sum of all variants).
    total_stock = (
        db.session.query(func.coalesce(func.sum(ProductVariant.stock), 0))
        .filter(ProductVariant.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    if stock_filter == "in":
        query = query.filter(total_stock > 0)
    elif stock_filter == "out":
        query = query.filter(total_stock == 0)
    elif stock_filter == "low":
        query = query.filter(total_stock > 0, total_stock <= 3)
    elif stock_filter == "inactive":
        query = query.filter(Product.is_active.is_(False))

    query = query.order_by(Product.created_at.desc(), Product.id.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        "admin/products.html",
        title="Admin — Products",
        pagination=pagination,
        products=pagination.items,
        search=search,
        category_filter=category_filter,
        stock_filter=stock_filter,
        all_categories=Category.query.order_by(Category.name).all(),
        thumb_url=_thumbnail_url,
    )


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    """Add a product. Variants come as parallel form rows (see JS in the form)."""
    form = ProductForm()

    if form.validate_on_submit():
        variants, variant_errors = _parse_variants_from_request()
        if variant_errors:
            for message in variant_errors:
                flash(message, "error")
        else:
            slug = (form.slug.data or "").strip()
            product = Product(
                name=form.name.data.strip(),
                slug=unique_slug(Product, slug or form.name.data),
                category_id=form.category_id.data,
                description=(form.description.data or "").strip(),
                fabric_care=(form.fabric_care.data or "").strip(),
                price=form.price.data,
                discount_price=form.discount_price.data,
                is_featured=bool(form.is_featured.data),
                is_new=bool(form.is_new.data),
                is_active=bool(form.is_active.data),
            )
            db.session.add(product)
            db.session.flush()  # get the product id for the variants

            _save_variants(product, variants)

            # Images uploaded together with the form (optional).
            errors = _handle_image_uploads(product, request.files.getlist("images"))
            db.session.commit()

            if errors:
                for message in errors:
                    flash(message, "error")
                flash(
                    f'Product "{product.name}" saved, but some images were rejected.',
                    "warning",
                )
            else:
                flash(f'Product "{product.name}" created.', "success")
            return redirect(url_for("admin.product_edit", product_id=product.id))

    return render_template(
        "admin/product_form.html",
        title="Admin — New product",
        form=form,
        product=None,
        variants_json="[]",
        images=[],
    )


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    """Edit a product, its variants and its images."""
    product = db.session.get(Product, product_id) or abort(404)
    form = ProductForm(obj=product, exclude_id=product.id)

    if form.validate_on_submit():
        variants, variant_errors = _parse_variants_from_request()
        if variant_errors:
            for message in variant_errors:
                flash(message, "error")
        else:
            slug = (form.slug.data or "").strip()
            product.name = form.name.data.strip()
            # Keep the old slug unless the admin typed a new one.
            product.slug = unique_slug(
                Product, slug or product.slug, exclude_id=product.id
            )
            product.category_id = form.category_id.data
            product.description = (form.description.data or "").strip()
            product.fabric_care = (form.fabric_care.data or "").strip()
            product.price = form.price.data
            product.discount_price = form.discount_price.data
            product.is_featured = bool(form.is_featured.data)
            product.is_new = bool(form.is_new.data)
            product.is_active = bool(form.is_active.data)

            _save_variants(product, variants)

            # Extra images uploaded with this save (optional).
            errors = _handle_image_uploads(product, request.files.getlist("images"))
            db.session.commit()

            if errors:
                for message in errors:
                    flash(message, "error")
            flash(f'Product "{product.name}" saved.', "success")
            return redirect(url_for("admin.product_edit", product_id=product.id))

    # Ready-made JSON for the variants editor (one JS row per variant).
    variants_json = json.dumps([
        {"id": v.id, "size": v.size, "colour": v.colour, "stock": v.stock}
        for v in product.variants
    ])

    return render_template(
        "admin/product_form.html",
        title=f"Admin — Edit {product.name}",
        form=form,
        product=product,
        variants_json=variants_json,
        images=sorted(product.images, key=lambda img: img.position),
    )


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    """Delete a product.

    - Has order items? -> soft delete (mark inactive) so old orders keep working.
    - No order items?  -> hard delete (row + images really go away).
    """
    product = db.session.get(Product, product_id) or abort(404)

    has_orders = OrderItem.query.filter_by(product_id=product.id).first() is not None

    if has_orders:
        product.is_active = False
        db.session.commit()
        flash(
            f'"{product.name}" has orders, so it was hidden from the store '
            "(set inactive) instead of being deleted.",
            "info",
        )
    else:
        # Remove every image file (Cloudinary or local disk) first.
        for image in list(product.images):
            delete_product_image_file(image.image_url, image.public_id)
        db.session.delete(product)
        db.session.commit()
        flash(f'Product "{product.name}" deleted.', "success")

    return redirect(url_for("admin.products"))


# ---------- product images ----------

def _handle_image_uploads(product, files):
    """Validate + save uploaded image files for a product.

    Returns a list of error messages (empty when everything went fine).
    The first image of a brand-new product becomes the main image automatically.
    """
    errors = []
    for file_storage in files:
        error = validate_image_file(file_storage)
        if error:
            errors.append(error)
            continue
        try:
            url, public_id = save_product_image(file_storage)
        except Exception as exc:  # Cloudinary/network trouble
            errors.append(f"Upload failed for {file_storage.filename}: {exc}")
            continue

        # New images go to the end of the gallery.
        next_pos = max(
            (img.position for img in product.images), default=-1
        ) + 1
        db.session.add(ProductImage(
            product=product,
            image_url=url,
            public_id=public_id,
            alt=product.name,
            position=next_pos,
        ))
    db.session.flush()
    return errors


@admin_bp.route("/products/<int:product_id>/images", methods=["POST"])
@admin_required
def product_images_upload(product_id):
    """Upload one or more extra images for an existing product."""
    product = db.session.get(Product, product_id) or abort(404)
    files = request.files.getlist("images")

    if not files or all(not f.filename for f in files):
        flash("Choose at least one image (JPG, PNG or WEBP, max 5 MB each).", "error")
        return redirect(url_for("admin.product_edit", product_id=product.id))

    errors = _handle_image_uploads(product, files)
    db.session.commit()

    if errors:
        for message in errors:
            flash(message, "error")
        flash("Some images were rejected — the rest were uploaded.", "warning")
    else:
        flash(f"{len(files)} image(s) uploaded.", "success")
    return redirect(url_for("admin.product_edit", product_id=product.id))


@admin_bp.route("/images/<int:image_id>/delete", methods=["POST"])
@admin_required
def image_delete(image_id):
    """Delete one image (file + database row)."""
    image = db.session.get(ProductImage, image_id) or abort(404)
    product_id = image.product_id

    delete_product_image_file(image.image_url, image.public_id)
    db.session.delete(image)
    db.session.flush()
    _renumber_images(product_id)
    db.session.commit()
    flash("Image deleted.", "success")
    return redirect(url_for("admin.product_edit", product_id=product_id))


@admin_bp.route("/images/<int:image_id>/main", methods=["POST"])
@admin_required
def image_set_main(image_id):
    """Make one image the main (first) image of the product."""
    image = db.session.get(ProductImage, image_id) or abort(404)
    product_id = image.product_id
    original_position = image.position

    # Shift everything else one step back, put this image at position 0.
    for other in ProductImage.query.filter_by(product_id=product_id).all():
        if other.id == image.id:
            other.position = -1  # temporary slot, fixed by renumber below
        elif other.position >= original_position:
            other.position += 1
    db.session.flush()
    _renumber_images(product_id)
    db.session.commit()
    flash("Main image updated.", "success")
    return redirect(url_for("admin.product_edit", product_id=product_id))


@admin_bp.route("/images/<int:image_id>/move", methods=["POST"])
@admin_required
def image_move(image_id):
    """Move one image left (-1) or right (+1) in the gallery order."""
    image = db.session.get(ProductImage, image_id) or abort(404)
    product_id = image.product_id

    direction = request.form.get("direction", "right")
    step = 1 if direction == "right" else -1

    siblings = sorted(
        ProductImage.query.filter_by(product_id=product_id).all(),
        key=lambda img: img.position,
    )
    index = next((i for i, img in enumerate(siblings) if img.id == image.id), None)
    target = index + step
    if index is not None and 0 <= target < len(siblings):
        # Swap positions with the neighbour.
        image.position, siblings[target].position = siblings[target].position, image.position
        db.session.flush()
        _renumber_images(product_id)
        db.session.commit()

    return redirect(url_for("admin.product_edit", product_id=product_id))


def _renumber_images(product_id):
    """Make positions 0,1,2,... with no gaps (position 0 = main image)."""
    images = sorted(
        ProductImage.query.filter_by(product_id=product_id).all(),
        key=lambda img: (img.position, img.id),
    )
    for i, image in enumerate(images):
        image.position = i
