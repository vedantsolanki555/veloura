"""Feature 3 tests: admin orders.

Covers:
- Orders list: search (order number / name / phone), status filter, newest first,
  pagination
- Order detail: customer, address, notes, snapshot items, totals, COD, history
- Status changes: forward moves, blocked backwards, frozen Cancelled/Delivered
- Cancel returns stock exactly once (never twice)
- Private admin note (shown in admin, never on the slip)
- WhatsApp customer link (wa.me + order number + status)
- Printable slip page
- CSV export with the current filters applied
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    Category,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    User,
    generate_order_number,
)

app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = True

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
    return m.group(1) if m else None


def login_admin(client):
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    client.post("/login", data={
        "csrf_token": csrf,
        "email": "admin@veloura.local",
        "password": "admin123",
    }, follow_redirects=True)


def logout(client):
    r = client.get("/account")
    csrf = extract_csrf(r.data) if r.status_code == 200 else None
    if csrf:
        client.post("/logout", data={"csrf_token": csrf})


def set_status(client, order, new_status):
    """Change an order's status through the real admin endpoint."""
    r = client.get(f"/admin/orders/{order.id}")
    csrf = extract_csrf(r.data)
    return client.post(
        f"/admin/orders/{order.id}/status",
        data={"csrf_token": csrf, "status": new_status},
        follow_redirects=True,
    )


def create_order(name="Test Customer", phone="9876543210", status="New",
                 items=None, email="", state="Maharashtra", notes="",
                 minutes_ago=0):
    """Build an order directly in the database (checkout is Step 4's job).

    `items` = list of (product, variant, quantity, price).
    Adds the initial 'New' history row like real checkout will.
    """
    lines = items or []
    subtotal = sum(float(price) * qty for _, _, qty, price in lines)
    shipping = 99 if subtotal < 1999 else 0
    order = Order(
        order_number=generate_order_number(),
        customer_name=name,
        phone=phone,
        email=email,
        address="12, Test Villa, MG Road",
        city="Pune",
        state=state,
        pincode="411001",
        notes=notes,
        status=status,
        subtotal=subtotal,
        shipping=shipping,
        payment_method="COD",
        total=subtotal + shipping,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.session.add(order)
    db.session.flush()

    for product, variant, qty, price in lines:
        db.session.add(OrderItem(
            order=order,
            product=product,
            variant=variant,
            quantity=qty,
            price=price,
            product_name=product.name,
            size=variant.size if variant else "",
            colour=variant.colour if variant else "",
        ))
    db.session.add(OrderStatusHistory(order=order, status=status,
                                      changed_by="system"))
    db.session.commit()
    return order


with app.app_context():
    db.create_all()

    # ---------- cleanup leftovers from earlier runs ----------
    old_orders = Order.query.filter(Order.customer_name.like("Test %")).all()
    old_ids = [o.id for o in old_orders]
    if old_ids:
        OrderStatusHistory.query.filter(
            OrderStatusHistory.order_id.in_(old_ids)).delete(
            synchronize_session=False)
        OrderItem.query.filter(OrderItem.order_id.in_(old_ids)).delete(
            synchronize_session=False)
        Order.query.filter(Order.id.in_(old_ids)).delete(
            synchronize_session=False)
    old_products = Product.query.filter(
        Product.slug.like("ord-test-%")).all()
    old_pids = [p.id for p in old_products]
    if old_pids:
        ProductVariant.query.filter(
            ProductVariant.product_id.in_(old_pids)).delete(
            synchronize_session=False)
        Product.query.filter(Product.id.in_(old_pids)).delete(
            synchronize_session=False)
    Category.query.filter(Category.name == "OrdTest").delete(
        synchronize_session=False)
    User.query.filter(User.email.like("test-admin3-%")).delete(
        synchronize_session=False)
    db.session.commit()

    print("\n=== Feature 3: Admin orders ===\n")

    # ---------- fixtures: one product with two variants ----------
    cat = Category(name="OrdTest", slug="ordtest")
    db.session.add(cat)
    db.session.flush()
    shirt = Product(name="Ord Test Shirt", slug="ord-test-shirt",
                    price=1000, category_id=cat.id)
    db.session.add(shirt)
    db.session.flush()
    size_m = ProductVariant(product=shirt, size="M", colour="Indigo", stock=5)
    size_l = ProductVariant(product=shirt, size="L", colour="Indigo", stock=3)
    db.session.add_all([size_m, size_l])
    db.session.commit()

    client = app.test_client()
    login_admin(client)

    # ---------- 1. Create orders ----------
    o_new = create_order(
        name="Test Alpha", phone="9876500001",
        items=[(shirt, size_m, 2, 1000)],
        email="alpha@example.com", notes="Ring the bell twice.",
        minutes_ago=5,
    )
    o_conf = create_order(
        name="Test Beta", phone="9876500002",
        items=[(shirt, size_l, 1, 1000)], minutes_ago=10,
    )
    create_order(
        name="Test Gamma", phone="9876500003",
        items=[(shirt, size_m, 1, 1000)], minutes_ago=15,
    )
    check("Order numbers are unique VLR- format",
          len({o_new.order_number, o_conf.order_number}) == 2
          and o_new.order_number.startswith("VLR-"))

    # ---------- 2. Orders list ----------
    r = client.get("/admin/orders")
    check("GET /admin/orders returns 200", r.status_code == 200)
    check("List shows order number", o_new.order_number.encode() in r.data)
    check("List shows customer name", b"Test Alpha" in r.data)
    check("List shows status badge", b"status-new" in r.data or b"New" in r.data)

    # Search by order number
    r = client.get(f"/admin/orders?q={o_new.order_number}")
    html = r.data.decode("utf-8")
    check("Search by order number finds it",
          o_new.order_number in html and "Test Beta" not in html)

    # Search by customer name
    r = client.get("/admin/orders?q=Test+Beta")
    html = r.data.decode("utf-8")
    check("Search by customer name finds it",
          "Test Beta" in html and "Test Alpha" not in html)

    # Search by phone
    r = client.get("/admin/orders?q=9876500003")
    check("Search by phone finds it", b"Test Gamma" in r.data)

    # Status filter
    r = client.get("/admin/orders?status=New")
    html = r.data.decode("utf-8")
    check("Status filter keeps New orders", "Test Alpha" in html)

    # ---------- 3. Status changes ----------
    r = set_status(client, o_conf, "Confirmed")
    db.session.expire_all()
    o_conf = db.session.get(Order, o_conf.id)
    check("New -> Confirmed works", o_conf.status == "Confirmed")

    r = client.get(f"/admin/orders/{o_conf.id}")
    html = r.data.decode("utf-8")
    check("History shows Confirmed with changed_by",
          "Confirmed" in html and "admin@veloura.local" in html)
    check("History length is 2 (New + Confirmed)",
          len(o_conf.status_history) == 2)

    # Confirmed -> Shipped -> Delivered
    set_status(client, o_conf, "Shipped")
    set_status(client, o_conf, "Delivered")
    db.session.expire_all()
    o_conf = db.session.get(Order, o_conf.id)
    check("Forward moves reach Delivered", o_conf.status == "Delivered")

    # Delivered is frozen — no going back
    r = set_status(client, o_conf, "Shipped")
    db.session.expire_all()
    o_conf = db.session.get(Order, o_conf.id)
    check("Delivered order cannot go back", o_conf.status == "Delivered"
          and b"cannot be changed" in r.data)

    # Backwards move on a live order is blocked
    r = set_status(client, o_conf, "Cancelled")
    db.session.expire_all()
    o_conf = db.session.get(Order, o_conf.id)
    check("Delivered order cannot be cancelled", o_conf.status == "Delivered")

    r = set_status(client, o_new, "Confirmed")
    r = set_status(client, o_new, "New")  # try to go back
    db.session.expire_all()
    o_new = db.session.get(Order, o_new.id)
    check("Confirmed cannot go back to New", o_new.status == "Confirmed"
          and b"Cannot move" in r.data)

    # ---------- 4. Cancel returns stock exactly once ----------
    stock_m_before = size_m.stock  # was 5, two Test Alpha orders took... (created directly, stock untouched)
    qty = 2
    r = set_status(client, o_new, "Cancelled")
    db.session.expire_all()
    o_new = db.session.get(Order, o_new.id)
    size_m = db.session.get(ProductVariant, size_m.id)
    check("Cancel moves status to Cancelled", o_new.status == "Cancelled")
    check("Cancel restores stock to variant", size_m.stock == stock_m_before + qty,
          f"(before {stock_m_before}, after {size_m.stock})")
    check("stock_restored flag set", o_new.stock_restored is True)

    # Second cancel attempt: frozen order — stock must NOT move again
    r = set_status(client, o_new, "Cancelled")
    db.session.expire_all()
    o_new = db.session.get(Order, o_new.id)
    size_m = db.session.get(ProductVariant, size_m.id)
    check("Second cancel blocked (order frozen)", o_new.status == "Cancelled"
          and b"cannot be changed" in r.data)
    check("Stock restored only once", size_m.stock == stock_m_before + qty,
          f"(stock now {size_m.stock})")

    # restore_stock double-call guard (direct API check)
    o_new.restore_stock()
    db.session.expire_all()
    size_m = db.session.get(ProductVariant, size_m.id)
    check("restore_stock() guard: third call is a no-op",
          size_m.stock == stock_m_before + qty)

    # Cancelled order shows no status buttons
    r = client.get(f"/admin/orders/{o_new.id}")
    check("Cancelled order hides status buttons",
          b"no further status" in r.data)

    # ---------- 5. Detail page content ----------
    r = client.get(f"/admin/orders/{o_new.id}")
    html = r.data.decode("utf-8")
    check("Detail shows customer name", "Test Alpha" in html)
    check("Detail shows phone", "9876500001" in html)
    check("Detail shows email", "alpha@example.com" in html)
    check("Detail shows address", "12, Test Villa, MG Road" in html)
    check("Detail shows city + pincode", "Pune" in html and "411001" in html)
    check("Detail shows customer notes", "Ring the bell twice." in html)
    check("Detail shows snapshot product name", "Ord Test Shirt" in html)
    check("Detail shows snapshot size/colour", ">M<" in html and "Indigo" in html)
    check("Detail shows subtotal/shipping/total labels",
          "Subtotal" in html and "Shipping" in html and "Total" in html)
    check("Detail shows COD payment method", "COD" in html)
    check("Detail shows WhatsApp button", b"WhatsApp customer" in r.data)
    check("Detail shows Print slip link", b"Print slip" in r.data)
    check("wa.me link present with country code",
          b"wa.me/" in r.data)

    # Snapshot beats live data: rename the product after the order
    shirt.name = "Ord Test Shirt RENAMED"
    db.session.commit()
    r = client.get(f"/admin/orders/{o_new.id}")
    check("Snapshot name survives product rename",
          b"Ord Test Shirt</td>" in r.data or b">Ord Test Shirt<" in r.data)
    shirt.name = "Ord Test Shirt"
    db.session.commit()

    # WhatsApp link contains order number + status (URL-encoded in href)
    m = re.search(r'href="(https://wa\.me/[^"]+)"', r.data.decode("utf-8"))
    check("WhatsApp href exists", m is not None)
    if m:
        from urllib.parse import unquote
        decoded = unquote(m.group(1))
        check("WhatsApp message has order number",
              o_new.order_number in decoded)
        check("WhatsApp message has status", "Cancelled" in decoded)

    # ---------- 6. Admin note (private) ----------
    r = client.get(f"/admin/orders/{o_new.id}")
    csrf = extract_csrf(r.data)
    r = client.post(f"/admin/orders/{o_new.id}/note",
                    data={"csrf_token": csrf,
                          "admin_note": "Customer asked to hold till Friday."},
                    follow_redirects=True)
    db.session.expire_all()
    o_new = db.session.get(Order, o_new.id)
    check("Admin note saved", "hold till Friday" in (o_new.admin_note or ""))
    check("Admin note shown on detail page", b"hold till Friday" in r.data)

    # ---------- 7. Printable slip ----------
    r = client.get(f"/admin/orders/{o_new.id}/slip")
    html = r.data.decode("utf-8")
    check("Slip page returns 200", r.status_code == 200)
    check("Slip shows order number", o_new.order_number in html)
    check("Slip shows item name", "Ord Test Shirt" in html)
    check("Slip shows totals", "Subtotal" in html and "Total" in html)
    check("Slip has print CSS", "@media print" in html)
    check("Slip has print button", b"window.print()" in r.data)
    check("Slip NEVER shows the internal admin note",
          "hold till Friday" not in html)

    # ---------- 8. CSV export ----------
    r = client.get("/admin/orders/export")
    check("CSV returns text/csv", r.mimetype == "text/csv")
    check("CSV is a download attachment",
          "attachment" in r.headers.get("Content-Disposition", ""))
    csv_text = r.data.decode("utf-8-sig")
    lines = [line for line in csv_text.strip().splitlines() if line]
    check("CSV header row correct",
          lines[0].startswith("Order number,Date,Customer,Phone,Email"))
    check("CSV contains all orders (no filter)",
          o_conf.order_number in csv_text and "Test Gamma" in csv_text)

    # Filters apply to the export
    r = client.get("/admin/orders/export?status=Cancelled")
    csv_cancelled = r.data.decode("utf-8-sig")
    check("CSV respects status filter",
          o_new.order_number in csv_cancelled
          and o_conf.order_number not in csv_cancelled)

    r = client.get("/admin/orders/export?q=Test+Gamma")
    csv_search = r.data.decode("utf-8-sig")
    check("CSV respects search filter",
          "Test Gamma" in csv_search and "Test Beta" not in csv_search)

    check("CSV rows carry snapshot fields",
          "Ord Test Shirt" in csv_search)

    # ---------- 9. Pagination + newest first ----------
    for i in range(12):
        create_order(name=f"Test Bulk {i:02d}", phone=f"987651{i:04d}",
                     items=[(shirt, size_l, 1, 1000)], minutes_ago=20 + i)
    r = client.get("/admin/orders?q=Test+Bulk")
    html = r.data.decode("utf-8")
    check("Pagination shows 2 pages", "Page 1 / 2" in html)
    # Newest first: among the bulk set, Bulk 00 was created last (least
    # minutes_ago) so it must appear above Bulk 01 on page 1.
    page1 = html.split("</tbody>")[0]
    check("Newest order listed first",
          page1.find("Test Bulk 00") != -1
          and page1.find("Test Bulk 00") < page1.find("Test Bulk 01"))
    r = client.get("/admin/orders?q=Test+Bulk&page=2")
    check("Page 2 loads", r.status_code == 200)

    # ---------- 10. Access control ----------
    logout(client)
    r = client.get("/admin/orders", follow_redirects=False)
    check("Anonymous /admin/orders redirects to /login",
          r.status_code == 302 and "/login" in r.headers.get("Location", ""))

    r = client.get("/register")
    csrf = extract_csrf(r.data)
    client.post("/register", data={
        "csrf_token": csrf, "name": "Nosy Customer",
        "email": "test-admin3-customer@example.com",
        "phone": "9876543219", "password": "secret123", "confirm": "secret123",
    }, follow_redirects=True)
    r = client.get("/admin/orders", follow_redirects=False)
    check("Customer /admin/orders gets 403", r.status_code == 403)
    r = client.get(f"/admin/orders/{o_conf.id}", follow_redirects=False)
    check("Customer order detail gets 403", r.status_code == 403)
    r = client.get(f"/admin/orders/{o_conf.id}/slip", follow_redirects=False)
    check("Customer slip page gets 403", r.status_code == 403)
    logout(client)

    # ---------- 11. Dashboard still works with orders present ----------
    login_admin(client)
    r = client.get("/admin")
    check("Dashboard loads with orders", r.status_code == 200)
    check("Dashboard recent orders link to detail",
          b"/admin/orders/" in r.data)

    # ---------- cleanup ----------
    logout(client)
    all_test_orders = Order.query.filter(Order.customer_name.like("Test %")).all()
    tids = [o.id for o in all_test_orders]
    if tids:
        OrderStatusHistory.query.filter(
            OrderStatusHistory.order_id.in_(tids)).delete(synchronize_session=False)
        OrderItem.query.filter(OrderItem.order_id.in_(tids)).delete(
            synchronize_session=False)
        Order.query.filter(Order.id.in_(tids)).delete(synchronize_session=False)
    ProductVariant.query.filter(
        ProductVariant.product_id == shirt.id).delete(synchronize_session=False)
    Product.query.filter(Product.id == shirt.id).delete(synchronize_session=False)
    Category.query.filter(Category.name == "OrdTest").delete(
        synchronize_session=False)
    User.query.filter(User.email.like("test-admin3-%")).delete()
    db.session.commit()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
