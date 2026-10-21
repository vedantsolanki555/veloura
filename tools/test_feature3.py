"""Feature 3 tests: session cart, COD checkout, orders, thank-you, CLI, My orders.

Covers the STEP4 Feature 3 test list:
    Add to cart, same variant twice, quantity above stock, update, remove,
    empty-cart checkout, invalid phone/pincode, valid order (guest and
    logged-in), stock reduced after order, out-of-stock during checkout,
    double-submit, thank-you page from another session, flask list-orders,
    My orders, CSRF, honeypot, admin status change + cancel-restores-stock.
"""

import os
import re
import sys
from datetime import datetime, timezone

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Order, OrderItem, OrderStatusHistory, Product, User, ProductVariant

app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = True  # test real CSRF tokens too


@app.before_request
def _reset_shared_request_state():
    """This script runs inside ONE app context, so per-request caches in `g`
    would leak across test clients:
    - flask-wtf's csrf_token (client B would render client A's token)
    - flask-login's _login_user (client B would appear logged-in as client A)
    Clear both before every request so each client behaves like a real,
    separate browser session."""
    from flask import g
    g.pop("csrf_token", None)
    g.pop("_login_user", None)

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {extra}")


def extract_csrf(html):
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    return m.group(1) if m else None


def clean_test_orders():
    """Delete orders left behind by earlier runs of this script."""
    old = Order.query.filter(Order.customer_name.like("Test F3%")).all()
    ids = [o.id for o in old]
    if ids:
        OrderStatusHistory.query.filter(OrderStatusHistory.order_id.in_(ids)).delete(synchronize_session=False)
        OrderItem.query.filter(OrderItem.order_id.in_(ids)).delete(synchronize_session=False)
        Order.query.filter(Order.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()


def add_to_cart(client, variant, quantity=1):
    """POST /cart/add with a real CSRF token (from the product page)."""
    r = client.get(f"/product/{variant.product_id}")
    csrf = extract_csrf(r.data)
    return client.post("/cart/add", data={
        "csrf_token": csrf,
        "variant_id": variant.id,
        "quantity": quantity,
    }, follow_redirects=True)


def checkout_page(client):
    r = client.get("/checkout")
    return extract_csrf(r.data), r


def place_order(client, name="Test F3 Guest", phone="9876543210",
                pincode="411001", extra=None):
    """POST /checkout with valid data + the page's CSRF + checkout token."""
    csrf, r = checkout_page(client)
    token_m = re.search(r'name="checkout_token"[^>]*value="([^"]+)"', r.data.decode())
    token = token_m.group(1) if token_m else ""
    data = {
        "csrf_token": csrf,
        "checkout_token": token,
        "name": name,
        "phone": phone,
        "email": "",
        "address": "12, Test Villa, MG Road",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": pincode,
        "notes": "Please ring the bell twice.",
    }
    if extra:
        data.update(extra)
    return client.post("/checkout", data=data, follow_redirects=True)


def fresh_stock_variant(min_stock=2):
    """Find (and return) a variant with at least min_stock of an active product."""
    return (
        ProductVariant.query.join(Product)
        .filter(Product.is_active.is_(True), ProductVariant.stock >= min_stock)
        .order_by(ProductVariant.id)
        .first()
    )


with app.app_context():
    db.create_all()

    # ---------- cleanup leftovers ----------
    clean_test_orders()
    User.query.filter(User.email.like("test-f3-%")).delete()
    db.session.commit()

    # Make sure the admin account exists (for the admin section).
    from werkzeug.security import generate_password_hash
    admin = User.query.filter_by(email="admin@veloura.local").first()
    if admin is None:
        admin = User(email="admin@veloura.local", is_admin=True,
                     password_hash=generate_password_hash("admin123"),
                     name="Admin", phone="9876543210")
        db.session.add(admin)
        db.session.commit()

    guest = app.test_client()   # a brand-new "browser" (no session)

    print("\n=== Feature 3: Cart, Checkout (COD) and Orders ===\n")

    # ================= cart basics =================
    r = guest.get("/cart")
    check("GET /cart returns 200", r.status_code == 200)
    check("Empty cart shows friendly state", b"Your cart is empty" in r.data)
    check("Empty cart has Continue shopping", b"Continue shopping" in r.data)

    # --- add to cart from the product page ---
    variant = fresh_stock_variant(3)
    original_stock = variant.stock
    r = add_to_cart(guest, variant, quantity=1)
    check("Add to cart redirects with success flash", b"Added to cart" in r.data)
    r = guest.get("/cart")
    # Product names can contain apostrophes (escaped differently by Jinja
    # vs html.escape) — check for a distinctive plain substring instead.
    check("Cart page shows the item",
          variant.product.name.split()[-1].encode() in r.data)
    check("Navbar cart badge shows 1", b'cart-badge">1<' in r.data)

    # --- same variant twice = quantity increases ---
    add_to_cart(guest, variant, quantity=1)
    with guest.session_transaction() as s:
        qty = s.get("cart", {}).get(str(variant.id))
    check("Same variant twice increases quantity", qty == 2, f"(got {qty})")

    # --- quantity above stock is capped ---
    guest2 = app.test_client()
    r = add_to_cart(guest2, variant, quantity=999)
    check("Quantity above stock is capped (message)",
          b"capped at" in r.data or b"only" in r.data.lower(), r.data[:200])
    with guest2.session_transaction() as s:
        qty = s.get("cart", {}).get(str(variant.id))
    check("Capped quantity equals variant stock", qty == original_stock, f"(got {qty})")

    # --- update quantity on /cart ---
    r = guest.get("/cart")
    csrf = extract_csrf(r.data)
    r = guest.post("/cart", data={"csrf_token": csrf, f"qty-{variant.id}": 1},
                   follow_redirects=True)
    with guest.session_transaction() as s:
        qty = s.get("cart", {}).get(str(variant.id))
    check("Cart update sets quantity", qty == 1, f"(got {qty})")
    check("Cart updated flash", b"Cart updated" in r.data)

    # --- CSRF rejected on cart add ---
    r = guest.post("/cart/add", data={"variant_id": variant.id, "quantity": 1})
    check("Cart add without CSRF is rejected", r.status_code == 400)

    # --- remove one item ---
    r = guest.get("/cart")
    csrf = extract_csrf(r.data)
    r = guest.post("/cart", data={"csrf_token": csrf, "remove": variant.id},
                   follow_redirects=True)
    check("Remove empties the cart", b"Item removed" in r.data and b"Your cart is empty" in r.data)

    # ================= checkout validation =================
    r = guest.get("/checkout", follow_redirects=False)
    check("Empty-cart checkout redirects to /cart",
          r.status_code == 302 and "/cart" in r.headers.get("Location", ""))

    # --- invalid phone + pincode ---
    add_to_cart(guest, variant, quantity=1)
    r = place_order(guest, phone="12345", pincode="AB")
    check("Invalid phone rejected", b"10-digit Indian mobile" in r.data)
    check("Invalid pincode rejected", b"6-digit pincode" in r.data)
    check("No order created on invalid form", Order.query.filter_by(customer_name="Test F3 Guest").count() == 0)

    # --- honeypot ---
    csrf, _ = checkout_page(guest)
    before = Order.query.count()
    place_order(guest, extra={"website": "http://spam.example"})
    check("Honeypot submission creates no order", Order.query.count() == before)

    # --- shipping maths on the summary (99 below 1999, free at/above) ---
    r = guest.get("/checkout")
    check("Checkout summary shows total", b"Total" in r.data)

    # ================= guest order =================
    stock_before = variant.stock
    r = place_order(guest, name="Test F3 Guest")
    order = Order.query.filter_by(customer_name="Test F3 Guest").first()
    check("Guest order created", order is not None)
    check("Order redirected to thank-you page",
          order is not None and f"/order/{order.order_number}/thanks" in r.request.path)
    check("Order status defaults to New", order is not None and order.status == "New")
    check("Payment method is COD", order is not None and order.payment_method == "COD")
    check("Guest order has no user_id", order is not None and order.user_id is None)
    check("Order number has VLR format",
          order is not None and re.fullmatch(r"VLR-\d{8}-\d{4}", order.order_number) is not None)
    check("Status history row created",
          order is not None and len(order.status_history) == 1
          and order.status_history[0].status == "New")
    check("Stock reduced after order", variant.stock == stock_before - 1,
          f"({stock_before} -> {variant.stock})")
    check("Cart emptied after order", b"Your cart is empty" in guest.get("/cart").data)
    check("Thank-you page shows order number",
          order is not None and order.order_number.encode() in r.data)
    check("Thank-you shows cash-on-delivery note", b"cash" in r.data.lower())
    check("Thank-you has WhatsApp button", b"wa.me" in r.data)

    # --- thank-you page from ANOTHER session = 403 ---
    if order is not None:
        r = guest2.get(f"/order/{order.order_number}/thanks", follow_redirects=False)
        check("Thank-you page blocked for another session", r.status_code == 403)

    # ================= out-of-stock during checkout =================
    add_to_cart(guest, variant, quantity=2)
    # Someone else buys the last pieces between cart and checkout:
    variant.stock = 1
    db.session.commit()
    r = place_order(guest, name="Test F3 Guest")
    check("Out-of-stock at checkout shows friendly message",
          b"only" in r.data.lower() or b"out of stock" in r.data.lower(), r.data[:200])
    check("Out-of-stock order rolled back (no 2nd order)",
          Order.query.filter_by(customer_name="Test F3 Guest").count() == 1)
    check("Stock unchanged after rollback", variant.stock == 1, f"(got {variant.stock})")
    # restore stock for later steps
    variant.stock = original_stock
    db.session.commit()

    # ================= double-submit =================
    # The 2nd submit of the SAME checkout form must not create a 2nd order.
    guest3 = app.test_client()
    add_to_cart(guest3, variant, quantity=1)
    csrf, page = checkout_page(guest3)
    token_m = re.search(r'name="checkout_token"[^>]*value="([^"]+)"', page.data.decode())
    token = token_m.group(1) if token_m else ""
    form = {
        "csrf_token": csrf,
        "checkout_token": token,
        "name": "Test F3 Double",
        "phone": "9876543210",
        "email": "",
        "address": "12, Test Villa, MG Road",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": "411001",
        "notes": "",
    }
    guest3.post("/checkout", data=form, follow_redirects=True)
    count_after_first = Order.query.filter_by(customer_name="Test F3 Double").count()
    guest3.post("/checkout", data=form, follow_redirects=True)
    count_after_second = Order.query.filter_by(customer_name="Test F3 Double").count()
    check("Double-submit creates only one order",
          count_after_first == 1 and count_after_second == 1,
          f"({count_after_first} then {count_after_second})")

    # ================= logged-in order =================
    buyer = app.test_client()
    r = buyer.get("/register")
    csrf = extract_csrf(r.data)
    buyer.post("/register", data={
        "csrf_token": csrf,
        "name": "Test F3 Buyer",
        "email": "test-f3-buyer@example.com",
        "phone": "9876543211",
        "password": "secret123",
        "confirm": "secret123",
    }, follow_redirects=True)
    add_to_cart(buyer, variant, quantity=1)
    r = place_order(buyer, name="Test F3 Buyer", phone="9876543211")
    logged_order = Order.query.filter_by(customer_name="Test F3 Buyer").first()
    user = User.query.filter_by(email="test-f3-buyer@example.com").first()
    check("Logged-in order created", logged_order is not None)
    check("Logged-in order linked to user",
          logged_order is not None and user is not None
          and logged_order.user_id == user.id)
    r = buyer.get("/account")
    check("My orders lists the order on /account",
          logged_order is not None and logged_order.order_number.encode() in r.data)
    check("My orders shows status chip", b"order-status" in r.data)

    # ================= flask list-orders =================
    runner = app.test_cli_runner()
    result = runner.invoke(args=["list-orders"])
    check("flask list-orders runs without error", result.exit_code == 0, result.output)
    check("list-orders shows the guest order",
          order is not None and order.order_number in result.output)
    check("list-orders shows customer name", "Test F3 Guest" in result.output)
    check("list-orders shows phone", "9876543210" in result.output)
    check("list-orders shows status", "New" in result.output)

    # ================= admin sees the order + status changes =================
    admin_client = app.test_client()
    r = admin_client.get("/login")
    csrf = extract_csrf(r.data)
    admin_client.post("/login", data={
        "csrf_token": csrf, "email": "admin@veloura.local", "password": "admin123",
    }, follow_redirects=True)

    r = admin_client.get("/admin/orders?q=Test F3 Guest")
    check("Admin orders list shows the new order",
          order is not None and order.order_number.encode() in r.data,
          f"(status={r.status_code})")

    # New -> Confirmed
    csrf = extract_csrf(admin_client.get(f"/admin/orders/{order.id}").data)
    admin_client.post(f"/admin/orders/{order.id}/status",
                      data={"csrf_token": csrf, "status": "Confirmed"},
                      follow_redirects=True)
    db.session.refresh(order)
    check("Admin can confirm the order", order.status == "Confirmed")
    check("Status history recorded Confirmed",
          any(h.status == "Confirmed" for h in order.status_history))

    # Confirmed -> Cancelled = stock restored exactly once
    variant_row = order.items[0].variant
    stock_now = variant_row.stock
    qty = order.items[0].quantity
    csrf = extract_csrf(admin_client.get(f"/admin/orders/{order.id}").data)
    admin_client.post(f"/admin/orders/{order.id}/status",
                      data={"csrf_token": csrf, "status": "Cancelled"},
                      follow_redirects=True)
    db.session.refresh(order)
    check("Admin can cancel the order", order.status == "Cancelled")
    check("Cancel restored the stock", variant_row.stock == stock_now + qty,
          f"({stock_now} -> {variant_row.stock})")
    check("stock_restored flag set once", order.stock_restored is True)

    # Cancelled orders are frozen — trying again must not restore stock twice
    csrf = extract_csrf(admin_client.get(f"/admin/orders/{order.id}").data)
    admin_client.post(f"/admin/orders/{order.id}/status",
                      data={"csrf_token": csrf, "status": "Cancelled"},
                      follow_redirects=True)
    check("Cancel-restores-stock never runs twice",
          variant_row.stock == stock_now + qty, f"(got {variant_row.stock})")

    # ================= final cleanup =================
    clean_test_orders()
    User.query.filter(User.email.like("test-f3-%")).delete()
    db.session.commit()

    print(f"\n=== Results: {PASS} passed, {FAIL} failed ===\n")
    sys.exit(1 if FAIL else 0)
