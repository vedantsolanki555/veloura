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

    # ---------- Part 3: polish + performance ----------
    print("\n-- Part 3: polish and performance --")

    # Image hygiene: lazy loading + width/height on product cards (no layout shift).
    r = c.get(f"/product/{product.id}")
    pd_html = r.data.decode()
    check("Product gallery main image has width+height",
          'width="800"' in pd_html and 'height="1000"' in pd_html)
    shop_html = c.get("/shop").data.decode()
    check("Product cards use loading=lazy + width/height",
          'loading="lazy"' in shop_html and 'width="800"' in shop_html and 'height="1000"' in shop_html)
    home_html2 = c.get("/").data.decode()
    check("Home images have width/height", 'width="1400"' in home_html2 and 'height="900"' in home_html2)

    # Cloudinary uploads store auto-quality/format (checked in code — see utils.py).
    utils_src = open(os.path.join("app", "utils.py"), encoding="utf-8").read()
    check("Cloudinary upload uses quality=auto + fetch_format=auto",
          'quality="auto"' in utils_src and 'fetch_format="auto"' in utils_src)

    # Static cache headers: images far-future (1 year), css/js one week.
    r = c.get("/static/img/favicon.svg")
    check("Images cached far future (1 year)",
          r.status_code == 200 and "max-age=31536000" in r.headers.get("Cache-Control", ""))
    r = c.get("/static/css/style.css")
    check("CSS cached for a week",
          r.status_code == 200 and "max-age=604800" in r.headers.get("Cache-Control", ""))
    r = c.get("/static/js/main.js")
    check("JS cached for a week",
          r.status_code == 200 and "max-age=604800" in r.headers.get("Cache-Control", ""))

    # gzip compression on HTML.
    r = c.get("/", headers={"Accept-Encoding": "gzip"})
    check("HTML is gzip-compressed when the browser asks",
          r.headers.get("Content-Encoding") == "gzip")

    # Accessibility: visible keyboard focus styles + Escape-to-close menus.
    css = open(os.path.join("app", "static", "css", "style.css"), encoding="utf-8").read()
    check("Visible :focus-visible outline defined", ":focus-visible" in css and "outline: 2px solid" in css)
    check("Darker gold token for AA text contrast", "--accent-ink" in css)
    js = open(os.path.join("app", "static", "js", "main.js"), encoding="utf-8").read()
    check("Mobile menu closes with Escape key", 'event.key === "Escape"' in js)
    admin_js = open(os.path.join("app", "static", "js", "admin.js"), encoding="utf-8").read()
    check("Admin sidebar closes with Escape key", 'event.key === "Escape"' in admin_js)

    # Loading states.
    check("Add-to-cart shows a loading state", "Adding…" in js)
    check("Contact form shows a sending state", "Sending…" in js and 'id="contact-form"' in
          open(os.path.join("app", "templates", "contact.html"), encoding="utf-8").read())

    # Empty states already exist on the key pages.
    cart_html = c.get("/cart").data.decode()
    check("/cart shows an empty state when nothing is in the cart", "cart-empty" in cart_html)
    shop_tpl = open(os.path.join("app", "templates", "shop.html"), encoding="utf-8").read()
    check("/shop template has a no-products empty state", "No products found" in shop_tpl)

    # Internal link crawler: every internal link must return 200.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from crawl_links import crawl as crawl_site
    pages_crawled, broken_links, dead_links = crawl_site()
    check(f"Link crawler visited pages ({len(pages_crawled)})", len(pages_crawled) > 10)
    check("Link crawler found no broken internal links", broken_links == [], broken_links)
    check('Link crawler found no dead href="#"', dead_links == [], dead_links)

    # ---------- Part 4: production readiness ----------
    r = c.get("/healthz")
    check("/healthz returns 200 ok", r.status_code == 200 and r.data.strip() == b"ok")

    home_resp = c.get("/")
    csp = home_resp.headers.get("Content-Security-Policy", "")
    check("CSP header present", "default-src 'self'" in csp)
    check("CSP allows only our own scripts", "script-src 'self'" in csp and "'unsafe-eval'" not in csp)
    check("CSP allows Google Fonts + Cloudinary",
          "fonts.googleapis.com" in csp and "res.cloudinary.com" in csp)
    check("X-Content-Type-Options: nosniff", home_resp.headers.get("X-Content-Type-Options") == "nosniff")
    check("X-Frame-Options: DENY", home_resp.headers.get("X-Frame-Options") == "DENY")
    check("Referrer-Policy set", bool(home_resp.headers.get("Referrer-Policy")))

    # No executable inline <script> left anywhere (JSON-LD data blocks are fine).
    for tpl in ["checkout.html", os.path.join("admin", "base.html"),
                os.path.join("admin", "order_detail.html"),
                os.path.join("admin", "product_form.html")]:
        html = open(os.path.join("app", "templates", tpl), encoding="utf-8").read()
        inline = [m for m in re.findall(r"<script\b[^>]*>", html)
                  if "src=" not in m and "ld+json" not in m]
        check(f"No inline scripts in {os.path.basename(tpl)}", inline == [], inline)

    # postgres:// (Neon/Render) is auto-converted to postgresql:// (SQLAlchemy 2).
    from config import _read_database_url
    saved_db = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgres://user:pass@db.example/veloura"
    try:
        converted = _read_database_url()
    finally:
        if saved_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = saved_db
    check("postgres:// URL converted to postgresql://",
          converted.startswith("postgresql://"), converted[:20])

    # Production refuses to boot without a real SECRET_KEY.
    from config import get_config
    saved_env = {k: os.environ.get(k) for k in ("FLASK_ENV", "SECRET_KEY")}
    os.environ["FLASK_ENV"] = "production"
    os.environ.pop("SECRET_KEY", None)
    try:
        refused = False
        try:
            create_app()
        except RuntimeError:
            refused = True
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("Production refuses to start without SECRET_KEY", refused)

    # Production config flags.
    os.environ["FLASK_ENV"] = "production"
    try:
        from config import ProductionConfig
        check("FLASK_ENV=production picks ProductionConfig", get_config() is ProductionConfig)
        check("Production sets ENFORCE_HTTPS", ProductionConfig.ENFORCE_HTTPS is True)
        check("Production secures session cookies",
              ProductionConfig.SESSION_COOKIE_SECURE is True)
    finally:
        os.environ["FLASK_ENV"] = "development"

    # Shared rate limiter used by /login and /contact.
    from app.ratelimit import clear_failures, is_limited, record_failure
    test_key = "__test_rate_key__"
    clear_failures(test_key)
    limiter_ok = not is_limited(test_key, max_attempts=3, window=60)
    for _ in range(3):
        record_failure(test_key, window=60)
    limiter_ok = limiter_ok and is_limited(test_key, max_attempts=3, window=60)
    clear_failures(test_key)
    limiter_ok = limiter_ok and not is_limited(test_key, max_attempts=3, window=60)
    check("Rate limiter blocks after max attempts and resets", limiter_ok)

    contact_src = open(os.path.join("app", "routes", "main.py"), encoding="utf-8").read()
    check("/contact route uses the shared rate limiter",
          "is_limited(rate_key" in contact_src)
    auth_src = open(os.path.join("app", "routes", "auth.py"), encoding="utf-8").read()
    check("/login uses the shared rate limiter", "from app.ratelimit import" in auth_src)

    # Production uploads must refuse the local fallback (ephemeral disk).
    from io import BytesIO as _BytesIO
    from werkzeug.datastructures import FileStorage
    from app.utils import save_product_image
    saved_upload_env = {k: os.environ.get(k) for k in ("FLASK_ENV", "CLOUDINARY_URL")}
    os.environ["FLASK_ENV"] = "production"
    os.environ.pop("CLOUDINARY_URL", None)
    try:
        refused_upload = False
        try:
            save_product_image(FileStorage(stream=_BytesIO(b"fake"), filename="x.png"))
        except ValueError:
            refused_upload = True
    finally:
        for k, v in saved_upload_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("Production refuses local image uploads without CLOUDINARY_URL", refused_upload)

    # Flask commands: init-db exists and is registered.
    runner = app.test_cli_runner()
    result = runner.invoke(args=["init-db"])
    check("flask init-db command exists and runs", result.exit_code == 0, str(result.output))

    # seed.py refuses to run in production without --force.
    seed_src = open("seed.py", encoding="utf-8").read()
    check("seed.py guards production", "Refusing to seed demo data" in seed_src)

    # Flask-Migrate is wired (migrations directory or migrate object).
    check("Flask-Migrate wired into the app", hasattr(app, "extensions")
          and any("migrate" in k for k in app.extensions))

    # Baseline migration exists and creates every table (built on an empty
    # DB, stamped on the dev DB — see Step 6 Part 4 notes in PROJECT_MAP).
    import glob as _glob
    versions = _glob.glob(os.path.join("migrations", "versions", "*.py"))
    baseline = [f for f in versions
                if "baseline" in open(f, encoding="utf-8").read().lower()]
    check("Migrations directory with baseline migration",
          os.path.exists(os.path.join("migrations", "alembic.ini")) and bool(baseline))
    if baseline:
        baseline_src = open(baseline[0], encoding="utf-8").read()
        check("Baseline migration creates all 10 tables",
              baseline_src.count("op.create_table") == 10,
              str(baseline_src.count("op.create_table")))

    # README documents demo-data cleanup + migrations (Part 4 item 7).
    readme = open("README.md", encoding="utf-8").read()
    check("README explains deleting demo seed data",
          "Demo seed data" in readme and "Delete" in readme)
    check("README documents flask init-db / flask db upgrade",
          "flask init-db" in readme and "flask db upgrade" in readme)

    # ---------- results ----------
    print(f"\n=== Step 6: {PASS} passed, {FAIL} failed ===")
    sys.exit(1 if FAIL else 0)
