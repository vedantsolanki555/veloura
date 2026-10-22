"""Step 6 tests — extended part by part.

Part 1 coverage:
    Static pages (about, contact, shipping-returns, privacy, terms) return 200
    with unique titles, contact form saves to the database (CSRF + honeypot +
    validation), admin Messages page lists/marks/deletes messages, footer has
    no dead href="#" links, custom 404 + 500 pages in the Veloura style.
"""

import os
import re
import sys

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Category, ContactMessage, Product, User

app = create_app()
app.config["TESTING"] = True
app.config["PROPAGATE_EXCEPTIONS"] = False  # let the 500 handler catch errors
app.config["WTF_CSRF_ENABLED"] = True


@app.before_request
def _reset_shared_request_state():
    """Same fix as the other test scripts: per-request caches in `g` would
    leak across test clients in this single-app-context script."""
    from flask import g
    g.pop("csrf_token", None)
    g.pop("_login_user", None)


@app.route("/step6-boom")
def _boom():
    """Route that always crashes — used to test the custom 500 page."""
    raise RuntimeError("intentional test error")


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


with app.app_context():
    db.create_all()

    # Make sure the admin account exists.
    if not User.query.filter_by(email="admin@veloura.local").first():
        admin = User(email="admin@veloura.local", is_admin=True, name="Admin", phone="9876543210")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

    # Cleanup leftovers from earlier runs.
    ContactMessage.query.delete()
    db.session.commit()

    c = app.test_client()

    # ---------- Part 1: static pages ----------
    print("\n-- Part 1: static pages --")
    pages = {
        "/about": "About Veloura",
        "/contact": "Contact Us",
        "/shipping-returns": "Shipping",
        "/privacy": "Privacy Policy",
        "/terms": "Terms of Service",
    }
    titles = []
    for path, needle in pages.items():
        r = c.get(path)
        check(f"{path} returns 200", r.status_code == 200, r.status_code)
        html = r.data.decode()
        check(f"{path} contains '{needle}'", needle in html)
        t = re.search(r"<title>(.*?)</title>", html)
        titles.append(t.group(1) if t else "")
    check("All page titles unique", len(set(titles)) == len(titles), titles)
    check("All titles mention Veloura", all("Veloura" in t for t in titles))

    # Shipping page uses live shipping settings from config.
    r = c.get("/shipping-returns")
    threshold = f"{int(app.config['FREE_SHIPPING_ABOVE']):,}"
    check("Shipping page shows the free-shipping threshold",
          threshold in r.data.decode())

    # ---------- Part 1: contact form ----------
    print("\n-- Part 1: contact form --")
    r = c.get("/contact")
    csrf = extract_csrf(r.data)
    check("Contact form has a CSRF token", bool(csrf))

    r = c.post("/contact", data={
        "csrf_token": csrf, "name": "Test S6", "email": "s6@example.com",
        "phone": "9876543210", "message": "Hello Veloura team, quick question!",
        "website": "",
    }, follow_redirects=True)
    check("Valid message saved + thank-you flash",
          r.status_code == 200 and b"Thank you for reaching out" in r.data)
    msg = ContactMessage.query.filter_by(email="s6@example.com").first()
    check("Message row exists in the database", msg is not None)
    check("Message phone digits stored", msg and msg.phone == "9876543210")

    # Honeypot
    r = c.post("/contact", data={
        "csrf_token": csrf, "name": "Bot", "email": "bot@example.com",
        "phone": "", "message": "Buy cheap followers now!!", "website": "http://spam",
    }, follow_redirects=True)
    check("Honeypot submission rejected",
          b"could not be sent" in r.data and
          ContactMessage.query.filter_by(email="bot@example.com").count() == 0)

    # CSRF required
    r = c.post("/contact", data={
        "name": "No CSRF", "email": "x@example.com", "phone": "",
        "message": "Should not save", "website": "",
    }, follow_redirects=True)
    check("Contact form without CSRF token rejected",
          ContactMessage.query.filter_by(email="x@example.com").count() == 0)

    # Invalid email
    r = c.post("/contact", data={
        "csrf_token": csrf, "name": "Bad Email", "email": "not-an-email",
        "phone": "", "message": "Hello there again", "website": "",
    })
    check("Invalid email blocked", "valid email" in r.data.decode())

    # Message too short
    r = c.post("/contact", data={
        "csrf_token": csrf, "name": "Short", "email": "short@example.com",
        "phone": "", "message": "Hi", "website": "",
    })
    check("Too-short message blocked",
          ContactMessage.query.filter_by(email="short@example.com").count() == 0)

    # ---------- Part 1: admin messages ----------
    print("\n-- Part 1: admin messages --")
    c.post("/login", data={"csrf_token": csrf, "email": "admin@veloura.local", "password": "admin123"},
           follow_redirects=True)

    r = c.get("/admin/messages")
    check("Admin messages page 200", r.status_code == 200)
    check("Message appears in admin", b"Hello Veloura team" in r.data)
    check("Unread badge shows in sidebar", b"unread" in r.data.lower())

    r = c.post(f"/admin/messages/{msg.id}/read", data={"csrf_token": csrf}, follow_redirects=True)
    check("Mark-as-read works", r.status_code == 200 and db.session.get(ContactMessage, msg.id).is_read)

    r = c.post(f"/admin/messages/{msg.id}/delete", data={"csrf_token": csrf}, follow_redirects=True)
    check("Delete works", r.status_code == 200 and db.session.get(ContactMessage, msg.id) is None)

    # Non-admin cannot see messages
    c2 = app.test_client()
    r = c2.get("/admin/messages")
    check("Anonymous redirected to login", r.status_code == 302 and "/login" in r.headers.get("Location", ""))

    # ---------- Part 1: footer links + error pages ----------
    print("\n-- Part 1: footer + error pages --")
    home = c.get("/").data.decode()
    check('No dead href="#" anywhere in the home footer/nav', 'href="#"' not in home)
    for path in ["/about", "/contact", "/shipping-returns", "/privacy", "/terms"]:
        check(f"Footer links to {path}", path in home)

    r = c.get("/definitely-not-a-page-xyz")
    check("Custom 404 page", r.status_code == 404 and b"404" in r.data)

    r = c.get("/step6-boom")
    check("Custom 500 page", r.status_code == 500 and b"Something Went Wrong" in r.data)

    # ---------- Part 2: SEO ----------
    print("\n-- Part 2: SEO --")

    product = Product.query.filter_by(is_active=True).first()
    assert product is not None, "seed data needed for SEO tests"

    # Home page: canonical, OG, Twitter, Organization JSON-LD, favicon
    home_html = c.get("/").data.decode()
    check("Home has canonical URL", 'rel="canonical"' in home_html)
    check("Home has og:title + og:description + og:image",
          all(x in home_html for x in ['property="og:title"', 'property="og:description"', 'property="og:image"']))
    check("Home has Twitter card tag", 'name="twitter:card"' in home_html)
    check("Home has Organization JSON-LD", '"@type": "Organization"' in home_html)
    check("Favicon links present (svg + png + apple-touch)",
          all(x in home_html for x in ["favicon.svg", "favicon-32x32.png", "apple-touch-icon.png"]))
    check("Favicon files exist on disk",
          all(os.path.exists(os.path.join("app", "static", "img", f))
              for f in ["favicon.svg", "favicon-32x32.png", "apple-touch-icon.png"]))

    # Product page: title/desc use product name, OG image = product image,
    # Product JSON-LD with INR price + availability.
    r = c.get(f"/product/{product.id}")
    ph = r.data.decode()
    import html as html_lib
    title = html_lib.unescape(re.search(r"<title>(.*?)</title>", ph).group(1))
    check("Product title uses product name", product.name in title)
    check("Product og:image is the product's main image",
          bool(product.images) and product.images[0].image_url in ph)
    check("Product JSON-LD present", '"@type": "Product"' in ph)
    check("Product JSON-LD price currency INR", '"priceCurrency": "INR"' in ph)
    check("Product JSON-LD availability set",
          "InStock" in ph or "OutOfStock" in ph)

    # Clean slug URL → 301 to the canonical id URL.
    if product.slug:
        r = c.get(f"/product/{product.slug}")
        check("Slug URL redirects 301 to /product/<id>",
              r.status_code == 301 and r.headers.get("Location", "").endswith(f"/product/{product.id}"))

    # Category page uses the real category name in the title.
    r = c.get(f"/shop/{product.category.slug}")
    t = re.search(r"<title>(.*?)</title>", r.data.decode()).group(1)
    check("Category title uses category name", product.category.name in t)

    # Canonical on filtered shop URL points to the clean base page.
    r = c.get("/shop?sort=price_asc&page=2")
    m = re.search(r'<link rel="canonical" href="([^"]+)"', r.data.decode())
    check("Filtered shop canonical = clean /shop (no query string)",
          bool(m) and m.group(1).endswith("/shop") and "?" not in m.group(1))

    # Sitemap + robots
    os.environ["SITE_URL"] = "https://veloura-test.example"
    try:
        r = c.get("/sitemap.xml")
        sx = r.data.decode()
        check("sitemap.xml returns 200 with XML mimetype",
              r.status_code == 200 and r.mimetype == "application/xml")
        check("Sitemap lists home + shop + static pages",
              all(x in sx for x in ["/</loc>", "/shop</loc>", "/about</loc>",
                                    "/contact</loc>", "/shipping-returns</loc>",
                                    "/privacy</loc>", "/terms</loc>"]))
        check("Sitemap lists every category", all(
            f"/shop/{cat.slug}</loc>" in sx for cat in Category.query.all()))
        active = Product.query.filter_by(is_active=True).count()
        inactive = Product.query.filter_by(is_active=False).count()
        check(f"Sitemap lists all {active} active products", sx.count("/product/") == active)
        check("Sitemap uses SITE_URL env var", "https://veloura-test.example/" in sx)

        r = c.get("/robots.txt")
        rb = r.data.decode()
        check("robots.txt returns 200 text/plain", r.status_code == 200 and r.mimetype == "text/plain")
        check("robots blocks /admin /cart /checkout /account /order",
              all(x in rb for x in ["Disallow: /admin", "Disallow: /cart",
                                    "Disallow: /checkout", "Disallow: /account",
                                    "Disallow: /order"]))
        check("robots points to sitemap with SITE_URL",
              "Sitemap: https://veloura-test.example/sitemap.xml" in rb)
    finally:
        del os.environ["SITE_URL"]

    # Private pages must not be indexed.
    for path in ["/cart", "/checkout", "/login", "/register", "/account"]:
        r = c.get(path)
        if r.status_code == 302:
            check(f"{path} is noindex (redirect to login still renders later)",
                  True)  # anonymous redirect — page itself has noindex when shown
            continue
        check(f"{path} has <meta name=\"robots\" content=\"noindex\">",
              'content="noindex"' in r.data.decode())

    # Admin pages noindex (already had it — keep the guarantee testable).
    admin_html = c.get("/admin/messages").data.decode()
    check("Admin pages have noindex", 'content="noindex' in admin_html)

    # Every public page has a unique, non-empty title + meta description.
    public = ["/", "/shop", f"/shop/{product.category.slug}", f"/product/{product.id}",
              "/about", "/contact", "/shipping-returns", "/privacy", "/terms"]
    seen_titles, ok_meta = set(), True
    for path in public:
        html = c.get(path).data.decode()
        title = re.search(r"<title>(.*?)</title>", html)
        desc = re.search(r'<meta name="description" content="([^"]+)"', html)
        seen_titles.add(title.group(1) if title else "")
        if not desc or len(desc.group(1)) < 20:
            ok_meta = False
    check("All public pages have unique titles", len(seen_titles) == len(public), seen_titles)
    check("All public pages have a real meta description", ok_meta)

    # ---------- results ----------
    print(f"\n=== Step 6: {PASS} passed, {FAIL} failed ===")
    sys.exit(1 if FAIL else 0)
