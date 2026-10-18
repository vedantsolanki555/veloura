"""Feature 1 tests: register, login, logout, /account, next-redirect, rate limit."""

import os
import re
import sys

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User

app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = True  # test real CSRF tokens too

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
    """Pull the csrf_token value out of an HTML page."""
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    return m.group(1) if m else None


def logout(client):
    """POST /logout with a valid CSRF token (taken from the account page form)."""
    r = client.get("/account")
    csrf = extract_csrf(r.data) if r.status_code == 200 else None
    if csrf:
        client.post("/logout", data={"csrf_token": csrf})


with app.app_context():
    db.create_all()
    User.query.filter(User.email.like("test-%")).delete()
    User.query.filter(User.email.like("ratelimit-%")).delete()
    db.session.commit()

    client = app.test_client()

    print("\n=== Feature 1: Customer Login ===\n")

    # --- 1. Register page loads ---
    r = client.get("/register")
    check("GET /register returns 200", r.status_code == 200)
    check("Register form has CSRF token", b"csrf_token" in r.data)

    # --- 2. Register a new user ---
    csrf = extract_csrf(r.data)
    r = client.post("/register", data={
        "csrf_token": csrf,
        "name": "Ravi Kumar",
        "email": "Test-User@Example.com",   # mixed case — must be stored lowercase
        "phone": "9876543210",
        "password": "secret123",
        "confirm": "secret123",
    }, follow_redirects=True)
    check("POST /register creates account", r.status_code == 200 and b"Welcome to Veloura" in r.data)
    user = User.query.filter_by(email="test-user@example.com").first()
    check("Email stored lowercase", user is not None)
    check("Auto-login after register", b"test-user@example.com" in r.data)

    # --- 3. Duplicate email rejected ---
    logout(client)
    r = client.get("/register")
    csrf = extract_csrf(r.data)
    r = client.post("/register", data={
        "csrf_token": csrf,
        "name": "Duplicate User",
        "email": "TEST-user@example.com",  # same email, different case
        "phone": "9876543211",
        "password": "secret123",
        "confirm": "secret123",
    })
    check("Duplicate email rejected (case-insensitive)", b"already exists" in r.data)

    # --- 4. Short password rejected ---
    r = client.get("/register")
    csrf = extract_csrf(r.data)
    r = client.post("/register", data={
        "csrf_token": csrf,
        "name": "Short Pass",
        "email": "short@example.com",
        "phone": "9876543212",
        "password": "short",
        "confirm": "short",
    })
    check("Password shorter than 8 rejected", b"between 8 and 256" in r.data)

    # --- 5. Password mismatch rejected ---
    r = client.get("/register")
    csrf = extract_csrf(r.data)
    r = client.post("/register", data={
        "csrf_token": csrf,
        "name": "Mismatch User",
        "email": "mismatch@example.com",
        "phone": "9876543213",
        "password": "secret123",
        "confirm": "different1",
    })
    check("Password mismatch rejected", b"do not match" in r.data)

    # --- 6. Wrong password -> generic error ---
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    r = client.post("/login", data={
        "csrf_token": csrf,
        "email": "test-user@example.com",
        "password": "wrongpassword",
    }, follow_redirects=True)
    check("Wrong password shows generic error", b"Invalid email or password" in r.data)

    # --- 7. Unknown email -> same generic error ---
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    r = client.post("/login", data={
        "csrf_token": csrf,
        "email": "nobody@example.com",
        "password": "whatever123",
    }, follow_redirects=True)
    check("Unknown email shows same generic error", b"Invalid email or password" in r.data)

    # --- 8. Correct login ---
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    r = client.post("/login", data={
        "csrf_token": csrf,
        "email": "test-user@example.com",
        "password": "secret123",
    }, follow_redirects=True)
    check("Correct login succeeds", b"Welcome back" in r.data)
    check("Navbar shows first name when logged in", b"Ravi" in r.data)

    # --- 9. /account accessible when logged in ---
    r = client.get("/account")
    check("GET /account returns 200 when logged in", r.status_code == 200)
    check("Account page shows email", b"test-user@example.com" in r.data)
    check("My orders placeholder visible", b"haven" in r.data)

    # --- 10. Logout ---
    csrf = extract_csrf(r.data)
    r = client.post("/logout", data={"csrf_token": csrf}, follow_redirects=True)
    check("POST /logout logs out and redirects home", r.status_code == 200 and b"Logout" not in r.data.split(b"nav-actions")[0] if b"nav-actions" in r.data else r.status_code == 200)

    # --- 11. /account redirects to login when logged out ---
    r = client.get("/account", follow_redirects=False)
    check("GET /account redirects when logged out", r.status_code == 302)
    check("Redirect goes to /login", "/login" in r.headers.get("Location", ""))

    # follow the redirect — login page renders
    r = client.get("/account", follow_redirects=True)
    check("Login page renders after redirect", r.status_code == 200 and b"Welcome back" in r.data)

    # --- 12. Bad "next" URLs are ignored ---
    for bad in ("https://evil.com", "//evil.com", "/\\evil.com"):
        logout(client)
        r = client.get(f"/login?next={bad}")
        csrf = extract_csrf(r.data)
        r = client.post(f"/login?next={bad}", data={
            "csrf_token": csrf,
            "email": "test-user@example.com",
            "password": "secret123",
        }, follow_redirects=False)
        loc = r.headers.get("Location", "")
        check(f"Malicious next ignored: {bad}", r.status_code == 302 and "evil.com" not in loc, f"-> {loc}")

    # --- 13. Valid same-site next is followed ---
    logout(client)
    r = client.get("/login?next=/shop")
    csrf = extract_csrf(r.data)
    r = client.post("/login?next=/shop", data={
        "csrf_token": csrf,
        "email": "test-user@example.com",
        "password": "secret123",
    }, follow_redirects=False)
    loc = r.headers.get("Location", "")
    check("Valid /shop next is followed", r.status_code == 302 and loc.endswith("/shop"), f"-> {loc}")

    # --- 14. CSRF required ---
    logout(client)
    r = client.post("/login", data={
        "email": "test-user@example.com",
        "password": "secret123",
    }, follow_redirects=False)
    check("Login without CSRF token is rejected (400)", r.status_code == 400)

    # --- 15. Rate limit: 5 failures then blocked ---
    for i in range(5):
        r = client.get("/login")
        csrf = extract_csrf(r.data)
        client.post("/login", data={
            "csrf_token": csrf,
            "email": "ratelimit@example.com",
            "password": "badpassword",
        }, follow_redirects=True)
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    r = client.post("/login", data={
        "csrf_token": csrf,
        "email": "ratelimit@example.com",
        "password": "badpassword",
    }, follow_redirects=True)
    check("6th failed login is rate-limited", b"Too many failed attempts" in r.data)

    # --- 16. Register without CSRF rejected ---
    r = client.post("/register", data={
        "name": "No CSRF",
        "email": "nocsrf@example.com",
        "phone": "9876543210",
        "password": "secret123",
        "confirm": "secret123",
    }, follow_redirects=False)
    check("Register without CSRF token is rejected (400)", r.status_code == 400)

    # --- 17. Navbar shows Login/Register when logged out ---
    r = client.get("/")
    check("Logged-out navbar shows Login", b">Login</a>" in r.data)
    check("Logged-out navbar shows Register", b"Register" in r.data)

    # --- 18. Logged-in navbar hides Login/Register ---
    logout(client)
    r = client.get("/login")
    csrf = extract_csrf(r.data)
    client.post("/login", data={
        "csrf_token": csrf,
        "email": "test-user@example.com",
        "password": "secret123",
    })
    r = client.get("/")
    check("Logged-in navbar has no Login link", b">Login</a>" not in r.data)
    check("Logged-in navbar has Logout button", b"Logout" in r.data)

    # --- 19. Admin user survived migration ---
    admin = User.query.filter_by(email="admin@veloura.local").first()
    check("Admin row survived migration", admin is not None)
    check("Admin password still works", admin is not None and admin.check_password("admin123"))

    # --- 20. Logout is POST-only ---
    r = client.get("/logout", follow_redirects=False)
    check("GET /logout rejected (405)", r.status_code == 405)

    # cleanup
    logout(client)
    User.query.filter(User.email.like("test-%")).delete()
    User.query.filter(User.email.like("ratelimit-%")).delete()
    db.session.commit()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
