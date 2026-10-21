"""
Database models (tables) for Veloura.

Each class below becomes one table in the database. Column names become
database column names automatically. Relationships let you write things
like product.images or order.items in Python instead of raw SQL.

Tables:
    User            — admin accounts (login comes in a later step)
    Category        — product categories (Men, Women, Kids, ...)
    Product         — items sold in the store
    ProductImage    — image URLs for a product
    ProductVariant  — size/colour/stock combinations of a product
    Order           — a customer's order
    OrderItem       — one line inside an order
"""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(UserMixin, db.Model):
    """Customer (and admin) account. Password is stored as a hash, never plain text.

    Admin rows may have NULL name/phone (they were created before customer
    login existed). Customer registrations always fill both in.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=True)
    # Email is always stored lowercase so "Ravi@X.com" and "ravi@x.com"
    # can never create two accounts.
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        """Hash the password and store the hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True if the given password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self):
        """First word of the full name — used in the navbar."""
        return (self.name or "").split(" ")[0] if self.name else ""

    def __repr__(self):
        return f"<User {self.email}>"


class Category(db.Model):
    """A product category, e.g. Men, Women, Kids."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    # slug is a URL-friendly version of the name (e.g. "men" for "Men").
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # One category has many products. "backref" lets you write category.products
    # from the Product side without extra code.
    products = db.relationship("Product", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    """One product for sale (e.g. a specific kurta design)."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    # Price in rupees. Numeric keeps exact decimal money values.
    price = db.Column(db.Numeric(10, 2), nullable=False)
    # Sale price. NULL means the product is not on discount.
    discount_price = db.Column(db.Numeric(10, 2), nullable=True)
    fabric_care = db.Column(db.Text, default="")
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_new = db.Column(db.Boolean, default=False, nullable=False)
    # Inactive products are hidden from the store (soft delete / hide).
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign key: which category this product belongs to.
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    # One product has many images and many variants.
    # Images always load in gallery order (position 0 first).
    images = db.relationship(
        "ProductImage",
        backref="product",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
    )
    variants = db.relationship(
        "ProductVariant", backref="product", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Product {self.name}>"


class ProductImage(db.Model):
    """One image URL belonging to a product."""

    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    # Cloudinary public_id (needed to delete/replace the image on Cloudinary).
    # NULL = the file lives locally in app/static/uploads/.
    public_id = db.Column(db.String(300), nullable=True)
    # Alt text read by screen readers (and shown if the image fails to load).
    alt = db.Column(db.String(300), default="", nullable=False)
    # Position controls display order (0 = first image).
    position = db.Column(db.Integer, default=0, nullable=False)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    def __repr__(self):
        return f"<ProductImage {self.id} product={self.product_id}>"


class ProductVariant(db.Model):
    """One size/colour/stock combination of a product.

    Example: "Blue / M / 5 pcs in stock" is one variant row.
    """

    __tablename__ = "product_variants"

    id = db.Column(db.Integer, primary_key=True)
    size = db.Column(db.String(20), nullable=False)    # e.g. S, M, L, XL, Free
    colour = db.Column(db.String(50), nullable=False)  # e.g. Indigo, Black
    stock = db.Column(db.Integer, default=0, nullable=False)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    def __repr__(self):
        return f"<ProductVariant {self.colour}/{self.size} stock={self.stock}>"


def generate_order_number():
    """A unique, non-guessable order number like VLR-20261021-4821.

    Used by checkout (Step 4) and by tests that build orders directly.
    Retries with fresh random digits until the number is free.
    """
    import random
    from datetime import datetime

    for _ in range(50):
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        digits = random.randint(1000, 9999)
        number = f"VLR-{today}-{digits}"
        if not Order.query.filter_by(order_number=number).first():
            return number
    # Extremely unlikely — fall back to an id-based number.
    return f"VLR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


class Order(db.Model):
    """A customer's order (COD). Admin manages it in Step 5 Feature 3."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    # Unique, non-guessable number shown to the customer and used in search.
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(80), nullable=True)
    pincode = db.Column(db.String(10), nullable=False)
    notes = db.Column(db.Text, default="")            # customer's delivery notes
    admin_note = db.Column(db.Text, default="")       # private owner-only note
    # Order status: New -> Confirmed -> Shipped -> Delivered (or Cancelled).
    status = db.Column(db.String(20), default="New", nullable=False)
    # Money breakdown.
    subtotal = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    shipping = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    payment_method = db.Column(db.String(20), default="COD", nullable=False)
    # True once a cancellation has already put items back into stock —
    # guarantees stock is restored exactly once, never twice.
    stock_restored = db.Column(db.Boolean, default=False, nullable=False)
    total = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Who placed it (NULL for guest checkout).
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # One order has many items. Deleting an order also deletes its items.
    items = db.relationship(
        "OrderItem", backref="order", lazy=True, cascade="all, delete-orphan"
    )
    # Every status change gets a row here (the "status history" timeline).
    status_history = db.relationship(
        "OrderStatusHistory",
        backref="order",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at",
    )

    @property
    def items_count(self):
        """Total number of pieces in this order."""
        return sum(item.quantity for item in self.items)

    def restore_stock(self):
        """Put every item's quantity back into its variant stock.

        Only called when an order is cancelled, and guarded by
        stock_restored so it can never run twice for the same order.
        """
        if self.stock_restored:
            return
        for item in self.items:
            if item.variant is not None:
                item.variant.stock += item.quantity
        self.stock_restored = True

    def __repr__(self):
        return f"<Order {self.order_number} {self.customer_name} {self.status}>"


class OrderStatusHistory(db.Model):
    """One entry in an order's status timeline.

    Example row: order 5 -> status "Shipped", changed by owner, 21 Oct 2026.
    """

    __tablename__ = "order_status_history"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False)
    # Email of the admin who made the change (or "system" for the first row).
    changed_by = db.Column(db.String(120), default="system", nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)

    def __repr__(self):
        return f"<OrderStatusHistory order={self.order_id} {self.status}>"


class OrderItem(db.Model):
    """One line inside an order: which product, how many, at what price.

    product_name / size / colour are SNAPSHOTS taken at order time — if the
    product or variant is edited or deleted later, the order still shows what
    the customer actually bought.
    """

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    # Price captured at order time (product price may change later).
    price = db.Column(db.Numeric(10, 2), nullable=False)

    # Snapshot fields (fall back to live product/variant data if empty).
    product_name = db.Column(db.String(200), default="", nullable=False)
    size = db.Column(db.String(20), default="", nullable=False)
    colour = db.Column(db.String(50), default="", nullable=False)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    # Optional: which size/colour was ordered. Can be NULL for simple orders.
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=True)

    product = db.relationship("Product")
    variant = db.relationship("ProductVariant")

    def __repr__(self):
        return f"<OrderItem order={self.order_id} product={self.product_id} x{self.quantity}>"


class Cart(db.Model):
    """Shopping cart row — table ready, logic comes in Phase 4. (No data yet.)"""

    __tablename__ = "cart"

    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)

    # Future links (user_id is NULL for guest cart until login exists).
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Cart {self.id} product={self.product_id} x{self.quantity}>"
