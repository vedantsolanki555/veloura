"""
Cart + checkout blueprint — Feature 3 (Step 4).

Routes:
    /cart                        View / update / remove cart lines
    /cart/add                    Add one variant (from the product page)
    /checkout                    COD checkout form + order creation
    /order/<order_number>/thanks Thank-you page (session-locked)

The order is created inside ONE database transaction that re-checks and
reduces stock — if anything is short, everything rolls back and the customer
sees a friendly message on the cart page.
"""

import os
import re
import secrets

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from app import cart as cart_lib
from app import db
from app.models import Order, OrderItem, OrderStatusHistory, ProductVariant, generate_order_number

cart_bp = Blueprint("cart", __name__)


# ---------- forms ----------

def _digits(value):
    """Keep only the digits of a phone/pincode (spaces and + are OK)."""
    return "".join(ch for ch in (value or "") if ch.isdigit())


class CheckoutForm(FlaskForm):
    """Delivery details for a Cash-on-Delivery order. Server never trusts the browser."""

    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField("Phone (10-digit mobile)", validators=[DataRequired(), Length(max=20)])
    email = StringField("Email (optional)", validators=[Optional(), Length(max=120)])
    address = TextAreaField("Address", validators=[DataRequired(), Length(min=5, max=500)])
    city = StringField("City", validators=[DataRequired(), Length(max=80)])
    state = StringField("State", validators=[DataRequired(), Length(max=80)])
    pincode = StringField("Pincode", validators=[DataRequired(), Length(max=10)])
    notes = TextAreaField("Order notes (optional)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Place order")

    def validate_phone(self, field):
        """Indian mobile numbers: 10 digits starting 6-9 (after stripping spaces)."""
        value = _digits(field.data)
        if not re.fullmatch(r"[6-9]\d{9}", value):
            raise ValidationError("Enter a valid 10-digit Indian mobile number.")

    def validate_pincode(self, field):
        if not re.fullmatch(r"\d{6}", _digits(field.data)):
            raise ValidationError("Enter a valid 6-digit pincode.")

    def validate_email(self, field):
        value = (field.data or "").strip()
        if value and (value.count("@") != 1 or "." not in value.split("@")[-1]):
            raise ValidationError("Enter a valid email address.")


# ---------- cart pages ----------

@cart_bp.route("/cart", methods=["GET", "POST"])
def view():
    """The cart page: update quantities, remove lines, see totals."""
    if request.method == "POST":
        # One form wraps every row. Buttons carry the variant they act on.
        if request.form.get("remove"):
            cart_lib.remove_item(request.form.get("remove"))
            flash("Item removed from cart.", "info")
        else:
            # Quantity inputs are named qty-<variant_id>.
            for key, value in request.form.items():
                if key.startswith("qty-"):
                    cart_lib.set_item_qty(key.split("-", 1)[1], value)
            flash("Cart updated.", "success")
        return redirect(url_for("cart.view"))

    lines = cart_lib.get_cart()
    subtotal, shipping, total = cart_lib.totals(lines)
    return render_template(
        "cart.html",
        title="Your cart",
        lines=lines,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        free_shipping_above=cart_lib.free_shipping_above(),
        has_problems=cart_lib.has_stock_problems(lines),
    )


@cart_bp.route("/cart/add", methods=["POST"])
def add():
    """Add one variant to the cart (posted by the product page)."""
    try:
        variant_id = int(request.form.get("variant_id", 0))
    except (TypeError, ValueError):
        variant_id = 0
    quantity = request.form.get("quantity", "1")

    ok, message = cart_lib.add_item(variant_id, quantity)
    flash(message, "success" if ok else "error")

    # Always land back on the product page for this variant.
    variant = db.session.get(ProductVariant, variant_id)
    if variant is not None:
        return redirect(url_for("main.product_detail", product_id=variant.product_id))
    return redirect(url_for("main.shop"))


# ---------- checkout ----------

def _checkout_token():
    """One-time token per checkout form — blocks accidental double submits."""
    token = session.get("checkout_token")
    if not token:
        token = secrets.token_hex(16)
        session["checkout_token"] = token
    return token


@cart_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    """Cash-on-Delivery checkout: validate, then create the order safely."""
    lines = cart_lib.get_cart()

    if not lines:
        flash("Your cart is empty — add something before checking out.", "info")
        return redirect(url_for("cart.view"))

    form = CheckoutForm()
    # Prefill from the account (logged-in users) or the last guest order.
    if request.method == "GET":
        if current_user.is_authenticated:
            form.name.data = current_user.name or ""
            form.phone.data = current_user.phone or ""
            form.email.data = current_user.email or ""
        else:
            last = session.get("last_customer") or {}
            form.name.data = last.get("name", "")
            form.phone.data = last.get("phone", "")
            form.email.data = last.get("email", "")
            form.address.data = last.get("address", "")
            form.city.data = last.get("city", "")
            form.state.data = last.get("state", "")
            form.pincode.data = last.get("pincode", "")

    subtotal, shipping, total = cart_lib.totals(lines)

    if form.validate_on_submit():
        # Honeypot: real people never see or fill this field.
        if request.form.get("website"):
            flash("Your order could not be placed. Please try again.", "error")
            return redirect(url_for("main.home"))

        # Same checkout token as the form the customer loaded? A second
        # submit of the SAME form (double-click) is sent back to the
        # first order's thank-you page instead of creating a duplicate.
        if request.form.get("checkout_token") != session.get("checkout_token"):
            last_number = session.get("last_order_number")
            if last_number:
                return redirect(url_for("cart.thanks", order_number=last_number))
            flash("This checkout form has already been used. Please try again.", "error")
            return redirect(url_for("cart.checkout"))

        if cart_lib.has_stock_problems(lines):
            flash("Some items in your cart just went out of stock. Please review your cart.", "error")
            return redirect(url_for("cart.view"))

        # ---- ONE database transaction: re-check stock, order, reduce stock ----
        try:
            order = _place_order(form, lines, subtotal, shipping, total)
        except ValueError as exc:   # our own "not enough stock" signal
            db.session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("cart.view"))

        # Success: empty the cart, retire the token, remember this order.
        cart_lib.clear_cart()
        session.pop("checkout_token", None)
        session["last_order_number"] = order.order_number
        placed = session.get("placed_orders", [])
        placed = (placed + [order.order_number])[-20:]   # keep the last 20
        session["placed_orders"] = placed
        # Remember guest details to prefill the NEXT checkout.
        session["last_customer"] = {
            "name": form.name.data, "phone": _digits(form.phone.data),
            "email": (form.email.data or "").strip(),
            "address": form.address.data, "city": form.city.data,
            "state": form.state.data, "pincode": _digits(form.pincode.data),
        }
        flash(f"Thank you! Your order {order.order_number} has been placed.", "success")
        return redirect(url_for("cart.thanks", order_number=order.order_number))

    return render_template(
        "checkout.html",
        title="Checkout",
        form=form,
        lines=lines,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        checkout_token=_checkout_token(),
        honeypot=True,
    )


def _place_order(form, lines, subtotal, shipping, total):
    """Create the Order inside one transaction that re-checks stock.

    Locks every variant row (FOR UPDATE on Postgres; SQLite serialises
    writes anyway), verifies stock, reduces it, writes the order + item
    snapshots + the first "New" status-history row, then commits.
    Raises ValueError with a friendly message if any stock is short —
    the caller rolls back, so nothing is saved.
    """
    variant_ids = [line["variant_id"] for line in lines]
    # Lock the rows so two simultaneous checkouts can't both pass the check.
    variants = (
        ProductVariant.query
        .filter(ProductVariant.id.in_(variant_ids))
        .with_for_update()
        .all()
    )
    stock_by_id = {v.id: v.stock for v in variants}

    for line in lines:
        available = stock_by_id.get(line["variant_id"], 0)
        if available < line["quantity"]:
            raise ValueError(
                f'Sorry, "{line["product"].name}" ({line["variant"].size}, '
                f'{line["variant"].colour}) has only {available} left. '
                "Please update your cart to continue."
            )

    order = Order(
        order_number=generate_order_number(),
        customer_name=form.name.data.strip(),
        phone=_digits(form.phone.data),
        email=(form.email.data or "").strip() or None,
        address=form.address.data.strip(),
        city=form.city.data.strip(),
        state=(form.state.data or "").strip(),
        pincode=_digits(form.pincode.data),
        notes=(form.notes.data or "").strip(),
        status="New",
        payment_method="COD",
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(order)

    for line in lines:
        # Snapshot = what the customer actually bought, even if the
        # product is renamed or deleted later.
        order.items.append(
            OrderItem(
                quantity=line["quantity"],
                price=line["unit_price"],
                product_name=line["product"].name,
                size=line["variant"].size,
                colour=line["variant"].colour,
                product_id=line["product"].id,
                variant_id=line["variant"].id,
            )
        )
        # Reduce stock inside the same transaction.
        variant = next(v for v in variants if v.id == line["variant_id"])
        variant.stock -= line["quantity"]

    # First entry of the status timeline (admin changes append more).
    db.session.add(
        OrderStatusHistory(status="New", changed_by="system", order=order)
    )

    db.session.commit()
    return order


# ---------- thank-you page ----------

@cart_bp.route("/order/<order_number>/thanks")
def thanks(order_number):
    """Order confirmation — only the session that placed the order may see it."""
    order = Order.query.filter_by(order_number=order_number).first_or_404()

    # Session lock: another browser/session gets a 403, even with the number.
    if order_number not in session.get("placed_orders", []):
        abort(403)

    # WhatsApp summary (wa.me link) — button hidden if the number is unset.
    raw_number = os.environ.get("WHATSAPP_NUMBER", "") or ""
    wa_number = "".join(ch for ch in raw_number if ch.isdigit())
    wa_message = "\n".join([
        "Hi! I just placed an order on Veloura:",
        f"Order: {order.order_number}",
        f"Items: {order.items_count}",
        f"Total: ₹{order.total}",
        "Payment: Cash on Delivery",
    ])
    wa_link = f"https://wa.me/{wa_number}?text={wa_message}" if wa_number else None

    return render_template(
        "order_thanks.html",
        title="Order placed",
        order=order,
        wa_link=wa_link,
    )
