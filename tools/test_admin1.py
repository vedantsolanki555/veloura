"""Feature 1 tests: admin access + dashboard.

Covers:
- make-admin CLI command
- /admin redirect for anonymous, 403 for normal customer, 200 for admin
- Navbar "Admin" link only visible to admins
- Dashboard numbers match the database
"""

import os
import re
import sys

# Windows console (cp1252) cannot print ₹ — force UTF-8 for test output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Category, Order, OrderItem, Product, ProductVariant, User

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


def login(client, email, password):
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    return client.post("/login", data={
        "csrf_token": csrf, "email": email, "password": password,
    }, follow_redirects=True)


def logout(client):
    r = client.get("/account")
    csrf = extract_csrf(r.data) if r.status_code == 200 else None
    if csrf:
        client.post("/logout", data={"csrf_token": csrf})


with app.app_context():
    db.create_all()

    # Clean up leftovers from earlier runs.
    User.query.filter(User.email.like("test-admin-%")).delete()
    db.session.commit()

    print("\n=== Feature 1: Admin access + dashboard ===\n")

    # ---------- 1. make-admin CLI ----------
    runner = app.test_cli_runner()

    # Non-existent email -> error
    result = runner.invoke(args=["make-admin", "nobody-here@example.com"])
    check("make-admin unknown email errors", result.exit_code != 0)

    # Create a normal user, promote them
    user = User(email="test-admin-customer@example.com", name="Test Admin Customer")
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    result = runner.invoke(args=["make-admin", "test-admin-customer@example.com"])
    db.session.expire_all()
    user = User.query.filter_by(email="test-admin-customer@example.com").first()
    check("make-admin promotes user", result.exit_code == 0 and user.is_admin is True)

    # Case-insensitive email
    user2 = User(email="test-admin-two@example.com", name="Test Two")
    user2.set_password("secret123")
    db.session.add(user2)
    db.session.commit()
    result = runner.invoke(args=["make-admin", "TEST-ADMIN-TWO@example.com"])
    db.session.expire_all()
    user2 = User.query.filter_by(email="test-admin-two@example.com").first()
    check("make-admin email case-insensitive", result.exit_code == 0 and user2.is_admin is True)

    # Running twice is safe (idempotent)
    result = runner.invoke(args=["make-admin", "test-admin-customer@example.com"])
    check("make-admin twice is safe", result.exit_code == 0)

    client = app.test_client()

    # ---------- 2. Anonymous user ----------
    r = client.get("/admin", follow_redirects=False)
    check("Anonymous /admin redirects to /login",
          r.status_code == 302 and "/login" in r.headers.get("Location", ""))

    # ---------- 3. Normal customer ----------
    # Register a fresh normal customer
    r = client.get("/register")
    csrf = extract_csrf(r.data)
    client.post("/register", data={
        "csrf_token": csrf,
        "name": "Normal Customer",
        "email": "test-admin-normal@example.com",
        "phone": "9876543210",
        "password": "secret123",
        "confirm": "secret123",
    }, follow_redirects=True)
    r = client.get("/admin", follow_redirects=False)
    check("Logged-in customer /admin gets 403", r.status_code == 403)

    # Customer navbar has NO Admin link
    r = client.get("/")
    check("Customer navbar has no Admin link", b'nav-admin' not in r.data)
    logout(client)

    # ---------- 4. Admin user ----------
    login(client, "test-admin-customer@example.com", "secret123")
    r = client.get("/admin", follow_redirects=False)
    check("Admin /admin returns 200", r.status_code == 200)
    check("Admin dashboard shows 'Dashboard' heading", b"Dashboard" in r.data)

    # Admin navbar HAS the Admin link
    r = client.get("/")
    check("Admin navbar shows Admin link", b'nav-admin' in r.data)

    # ---------- 5. Dashboard numbers match the database ----------
    r = client.get("/admin")
    html = r.data.decode("utf-8")

    total_products = Product.query.count()
    total_categories = Category.query.count()
    total_orders = Order.query.count()

    check("Dashboard product count matches DB",
          f'>{total_products}<' in html, f"(expected {total_products})")
    check("Dashboard category count matches DB",
          f'>{total_categories}<' in html, f"(expected {total_categories})")
    check("Dashboard order count matches DB",
          f'>{total_orders}<' in html, f"(expected {total_orders})")

    # Total sales = sum of non-cancelled order totals
    expected_sales = float(
        db.session.query(db.func.coalesce(db.func.sum(Order.total), 0))
        .filter(Order.status != "Cancelled").scalar() or 0
    )
    # Dashboard shows Indian format via the inr filter
    from app import inr as inr_filter
    check("Dashboard total sales matches DB (formatted)",
          inr_filter(expected_sales) in html, f"(expected {inr_filter(expected_sales)})")

    # Low-stock section exists
    low_stock_count = ProductVariant.query.filter(ProductVariant.stock <= 3).count()
    check("Dashboard low-stock section present", "Low stock" in html)
    if low_stock_count:
        check("Low-stock rows rendered", "stock-low" in html or "stock-zero" in html)

    # Recent orders section exists (empty-state message if no orders)
    check("Dashboard recent orders section present",
          "Recent orders" in html)

    # Status pills for all five statuses
    for status in ["New", "Confirmed", "Shipped", "Delivered", "Cancelled"]:
        check(f"Dashboard shows status pill: {status}", status in html)

    # ---------- 6. Sidebar ----------
    check("Sidebar has Dashboard link", "Dashboard" in html)
    check("Sidebar has Products link", "/admin/products" in html)
    check("Sidebar has Categories link", "/admin/categories" in html)
    check("Sidebar has Orders link", "/admin/orders" in html)
    check("Sidebar has View store link", "View store" in html)
    check("Sidebar has Logout button", "Logout" in html)

    # ---------- 7. Login next-redirect to /admin works ----------
    logout(client)
    r = client.get("/login?next=%2Fadmin")
    csrf = extract_csrf(r.data)
    r = client.post("/login?next=%2Fadmin", data={
        "csrf_token": csrf,
        "email": "test-admin-customer@example.com",
        "password": "secret123",
    }, follow_redirects=False)
    check("Admin login with ?next=/admin redirects to /admin",
          r.status_code == 302 and r.headers.get("Location", "").rstrip("/").endswith("/admin"))

    # ---------- cleanup ----------
    logout(client)
    User.query.filter(User.email.like("test-admin-%")).delete()
    db.session.commit()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
