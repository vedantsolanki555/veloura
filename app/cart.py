"""
Session shopping cart — Feature 3 (Step 4).

The cart lives in the Flask session (a signed cookie), NOT in the database.
That means:
    - guests can add items without an account
    - no "cart" rows to clean up
    - the same helpers work for logged-in users and guests

Session format:  session["cart"] = { variant_id(str) : quantity(int) }

Money rules:
    - unit price = discount price if set, else full price
    - shipping is SHIPPING_FEE (env, default ₹99)
    - shipping is FREE when the subtotal reaches FREE_SHIPPING_ABOVE (env,
      default ₹1,999)
"""

import os
from decimal import Decimal

from flask import session
from sqlalchemy.orm import selectinload

from app.models import Product, ProductVariant

# Key used inside the session cookie.
CART_KEY = "cart"


# ---------- shipping settings (environment variables) ----------

def shipping_fee():
    """Shipping charge when the order is below the free-shipping threshold."""
    try:
        return Decimal(os.environ.get("SHIPPING_FEE", "99"))
    except Exception:
        return Decimal("99")


def free_shipping_above():
    """Subtotal at (or above) which shipping becomes free."""
    try:
        return Decimal(os.environ.get("FREE_SHIPPING_ABOVE", "1999"))
    except Exception:
        return Decimal("1999")


# ---------- low-level session access ----------

def _raw_cart():
    """The cart dict as stored in the session (variant_id str -> qty)."""
    raw = session.get(CART_KEY)
    if not isinstance(raw, dict):
        raw = {}
    # Normalise keys to strings and quantities to positive ints.
    clean = {}
    for key, qty in raw.items():
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            clean[str(int(key))] = qty
    return clean


def _save_cart(cart):
    if cart:
        session[CART_KEY] = cart
    else:
        session.pop(CART_KEY, None)
    session.modified = True


def cart_count():
    """Total number of pieces in the cart — used for the navbar badge."""
    return sum(_raw_cart().values())


# ---------- cart reads (with live product data) ----------

def get_cart():
    """Every cart line joined with live product / variant data.

    Returns a list of dicts:
        variant     ProductVariant row (may be None if it was deleted)
        product     Product row (may be None if the variant is gone)
        quantity    what the customer wants
        unit_price  effective price (discount price if set)
        line_total  unit_price * quantity
        max_stock   current stock of the variant
        problem     None if the line is fine, else a friendly message
                    ("Out of stock", "Only 2 left", product hidden, ...)
    """
    cart = _raw_cart()
    if not cart:
        return []

    variant_ids = [int(vid) for vid in cart]
    # One query for all variants + their products + first image (no N+1).
    variants = (
        ProductVariant.query.options(
            selectinload(ProductVariant.product).selectinload(Product.images)
        )
        .filter(ProductVariant.id.in_(variant_ids))
        .all()
    )
    by_id = {v.id: v for v in variants}

    lines = []
    for vid_str, qty in cart.items():
        variant = by_id.get(int(vid_str))
        if variant is None:
            # Variant deleted from the catalogue — drop it silently.
            continue
        product = variant.product
        unit_price = Decimal(product.discount_price if product.discount_price is not None else product.price)

        problem = None
        if not product.is_active:
            problem = "This item is no longer available."
        elif variant.stock <= 0:
            problem = "Out of stock."
        elif variant.stock < qty:
            problem = f"Only {variant.stock} left."

        lines.append({
            "variant": variant,
            "product": product,
            "variant_id": variant.id,
            "quantity": qty,
            "unit_price": unit_price,
            "line_total": unit_price * qty,
            "max_stock": variant.stock,
            "problem": problem,
            "image_url": product.images[0].image_url if product.images else None,
        })
    return lines


def totals(lines):
    """(subtotal, shipping, total) for a list of cart lines."""
    subtotal = sum((line["line_total"] for line in lines), Decimal("0"))
    shipping = Decimal("0") if subtotal >= free_shipping_above() else shipping_fee()
    # Free shipping on an empty cart keeps the empty page simple.
    if subtotal == 0:
        shipping = Decimal("0")
    return subtotal, shipping, subtotal + shipping


def has_stock_problems(lines):
    """True if any line is out of stock / below requested quantity."""
    return any(line["problem"] for line in lines)


# ---------- cart writes ----------

def add_item(variant_id, quantity=1):
    """Add a variant to the cart. Same variant twice = quantity increases.

    Quantity is clamped to the variant's stock (never exceeds it).
    Returns (ok, message):
        ok=False  — nothing was added (bad variant, out of stock, ...)
        ok=True   — the message describes what happened (incl. clamping)
    """
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, quantity)

    variant = ProductVariant.query.get(variant_id)
    if variant is None:
        return False, "That item could not be found."
    if not variant.product.is_active:
        return False, "This item is no longer available."
    if variant.stock <= 0:
        return False, "Sorry, that item is out of stock."

    cart = _raw_cart()
    key = str(variant.id)
    new_qty = cart.get(key, 0) + quantity
    if new_qty > variant.stock:
        # Never let the cart hold more than what is actually in stock.
        if cart.get(key, 0) >= variant.stock:
            return False, f"Only {variant.stock} of this item are available."
        new_qty = variant.stock
        cart[key] = new_qty
        _save_cart(cart)
        return True, f"Quantity was capped at {variant.stock} — that is all the stock left."
    cart[key] = new_qty
    _save_cart(cart)
    return True, "Added to cart."


def set_item_qty(variant_id, quantity):
    """Set one line's quantity (0 = remove). Clamped to current stock."""
    cart = _raw_cart()
    key = str(int(variant_id))
    if key not in cart:
        return
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1
    variant = ProductVariant.query.get(int(variant_id))
    max_stock = variant.stock if variant else 0
    quantity = max(0, min(quantity, max_stock))
    if quantity == 0:
        cart.pop(key, None)
    else:
        cart[key] = quantity
    _save_cart(cart)


def remove_item(variant_id):
    """Remove one variant from the cart."""
    cart = _raw_cart()
    cart.pop(str(int(variant_id)), None)
    _save_cart(cart)


def clear_cart():
    """Empty the cart (after an order is placed)."""
    session.pop(CART_KEY, None)
    session.modified = True
