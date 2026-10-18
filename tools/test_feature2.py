"""Feature 2 tests: cloth list — filters, sort, search, pagination, badges, no N+1."""

import os
import re
import sys

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import create_app, db
from app.models import Product, ProductVariant

app = create_app()
app.config["TESTING"] = True

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


# ---------- query counter (N+1 guard) ----------
_queries = []


@event.listens_for(Engine, "before_cursor_execute")
def _count_queries(conn, cursor, statement, parameters, context, executemany):
    _queries.append(statement)


def count_queries(fn):
    """Run fn() and return how many SQL statements it caused."""
    _queries.clear()
    fn()
    return len(_queries)


def product_names(html):
    """Product names visible on a shop page (from card titles)."""
    import html as html_mod
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    return [html_mod.unescape(n)
            for n in re.findall(r'card-title">\s*<a[^>]*>([^<]+)</a>', html)]


with app.app_context():
    db.create_all()
    client = app.test_client()

    total_products = Product.query.count()
    print(f"\n=== Feature 2: Cloth List ({total_products} products in DB) ===\n")

    # --- 1. Basic pages load ---
    r = client.get("/")
    check("GET / returns 200", r.status_code == 200)
    check("Home has Featured section", b"Featured" in r.data)
    check("Home has New Arrivals section", b"New Arrivals" in r.data)

    r = client.get("/shop")
    check("GET /shop returns 200", r.status_code == 200)
    check("Shop shows result count", b"product" in r.data or b"result" in r.data)

    r = client.get("/shop/men")
    check("GET /shop/men returns 200", r.status_code == 200)
    r = client.get("/shop/women")
    check("GET /shop/women returns 200", r.status_code == 200)
    r = client.get("/shop/kids")
    check("GET /shop/kids returns 200", r.status_code == 200)
    r = client.get("/shop/accessories")
    check("GET /shop/accessories returns 200", r.status_code == 200)
    r = client.get("/shop/nope")
    check("Unknown category is 404", r.status_code == 404)

    # --- 2. Pagination: 12 per page ---
    r = client.get("/shop")
    names_p1 = product_names(r.data)
    check("Page 1 shows max 12 products", len(names_p1) <= 12)
    if total_products > 12:
        check("Page 1 shows exactly 12 (more products exist)", len(names_p1) == 12,
              f"got {len(names_p1)}")
        check("Page 1 shows 'Showing 1–12'",
              b"Showing 1" in r.data and b"12" in r.data)
        check("Pagination nav present", b'class="pagination"' in r.data)
        r2 = client.get("/shop?page=2")
        check("GET /shop?page=2 returns 200", r2.status_code == 200)
        names_p2 = product_names(r2.data)
        check("Page 2 has different products", set(names_p1) != set(names_p2))
        check("Page 2 keeps to 12 max", len(names_p2) <= 12)
        # Out-of-range page falls back to last real page (no crash, not empty)
        last = (total_products + 11) // 12
        r3 = client.get(f"/shop?page={last + 50}")
        check("Huge page number still returns 200", r3.status_code == 200)
        check("Huge page number shows last page items (not empty)",
              len(product_names(r3.data)) > 0)
    else:
        check("Small catalogue: single page, no crash", len(names_p1) == total_products)

    # --- 3. Sort ---
    r = client.get("/shop?sort=price_asc")
    check("sort=price_asc returns 200", r.status_code == 200)
    check("sort select remembers price_asc", b'value="price_asc" selected' in r.data)
    r = client.get("/shop?sort=price_desc")
    check("sort=price_desc returns 200", r.status_code == 200)
    check("sort select remembers price_desc", b'value="price_desc" selected' in r.data)
    r = client.get("/shop?sort=garbage")
    check("Unknown sort falls back to newest (200)", r.status_code == 200)
    # Verify real ordering for price_asc using DB effective price
    from sqlalchemy import func
    eff = func.coalesce(Product.discount_price, Product.price)
    cheapest = Product.query.order_by(eff.asc()).first().name
    names = product_names(client.get("/shop?sort=price_asc").data)
    check("price_asc actually puts cheapest first", names and names[0] == cheapest,
              f"first={names[0] if names else None} expected={cheapest}")
    priciest = Product.query.order_by(eff.desc()).first().name
    names = product_names(client.get("/shop?sort=price_desc").data)
    check("price_desc actually puts priciest first", names and names[0] == priciest,
              f"first={names[0] if names else None} expected={priciest}")

    # --- 4. Price filter ---
    r = client.get("/shop?min=500&max=2000")
    check("Price filter min/max returns 200", r.status_code == 200)
    in_range = Product.query.filter(eff >= 500, eff <= 2000).count()
    shown_total = len(product_names(r.data))
    check("Price filter result count matches DB", shown_total == min(in_range, 12),
              f"shown={shown_total} db={in_range}")
    check("min input keeps its value", b'value="500"' in r.data)
    check("max input keeps its value", b'value="2000"' in r.data)

    # --- 5. Search ---
    r = client.get("/shop?q=kurta")
    check("Search q=kurta returns 200", r.status_code == 200)
    check("Search shows query text", b"kurta" in r.data.lower())
    r = client.get("/shop?q=zzzz-no-such-product")
    check("Empty search results return 200", r.status_code == 200)
    check("Empty search shows friendly empty state", b"No products found" in r.data)

    # --- 6. Size + colour filters ---
    some_variant = ProductVariant.query.filter(ProductVariant.stock >= 0).first()
    r = client.get(f"/shop?size={some_variant.size}")
    check("Size filter returns 200", r.status_code == 200)
    names = product_names(r.data)
    ok = all(
        Product.query.filter_by(name=n).first().variants
        and any(v.size == some_variant.size for v in Product.query.filter_by(name=n).first().variants)
        for n in names
    ) if names else True
    check("Every product on size filter page has that size", ok)
    check("Active size chip highlighted",
          f'class="filter-chip active">{some_variant.size}'.encode() in r.data
          or f'>{some_variant.size}</a>' in r.data)

    r = client.get(f"/shop?colour={some_variant.colour}")
    check("Colour filter returns 200", r.status_code == 200)
    names = product_names(r.data)
    ok = all(
        any(v.colour == some_variant.colour
            for v in Product.query.filter_by(name=n).first().variants)
        for n in names
    ) if names else True
    check("Every product on colour filter page has that colour", ok)

    r = client.get("/shop?size=NOPE123&colour=NOPE456")
    check("Bogus size+colour = empty state (200)", r.status_code == 200 and b"No products found" in r.data)

    # --- 7. Filters preserved across sort / search / pagination ---
    r = client.get("/shop/men?size=M&colour=Indigo&min=100&max=99999&sort=price_asc&q=kurta")
    check("Combined filter URL returns 200", r.status_code == 200)
    body = r.data.decode("utf-8")
    check("size kept in sort form", 'name="size" value="M"' in body)
    check("colour kept in sort form", 'name="colour" value="Indigo"' in body)
    check("search kept in sort form", 'name="q" value="kurta"' in body)
    check("category chips keep size filter", "size=M" in body)

    # --- 8. Product cards: hover image + out-of-stock badge + lazy images ---
    r = client.get("/shop")
    body = r.data.decode("utf-8")
    check("Cards lazy-load images", 'loading="lazy"' in body)
    check("Card shows Sale or New or OOS badge",
          ("badge-sale" in body or ">New<" in body or "badge-oos" in body))
    oos = Product.query.filter(
        Product.id.not_in(
            db.session.query(ProductVariant.product_id).filter(ProductVariant.stock > 0)
        )
    ).first()
    if oos:
        r = client.get(f"/shop?q={oos.name.split()[0]}")
        check("Out-of-stock product shows OOS badge", b"badge-oos" in r.data or b"Out of stock" in r.data,
              f"product={oos.name}")
    else:
        check("No fully out-of-stock product in DB (badge skip)", True)
    # Second image on hover when a product has 2+ images
    multi = Product.query.filter(Product.id.in_(
        db.session.query(ProductVariant.product_id)
    )).all()
    from app.models import ProductImage
    multi = Product.query.join(ProductImage).group_by(Product.id).having(
        func.count(ProductImage.id) >= 2).first()
    if multi:
        r = client.get(f"/shop?q={multi.name}")
        check("Card renders hover second image", 'card-img-hover' in r.data.decode("utf-8"),
              f"product={multi.name}")
    else:
        check("No product with 2+ images (hover skip)", True)

    # --- 9. Mobile layout CSS present ---
    css = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css"),
               encoding="utf-8").read()
    check("CSS: 2-column mobile grid", "repeat(2, 1fr)" in css)
    check("CSS: pagination styled", ".pagination" in css and ".page-link" in css)

    # --- 10. N+1 guard: /shop must not run one query per product ---
    n = count_queries(lambda: client.get("/shop"))
    check(f"No N+1 on /shop (queries={n}, products={total_products})", n < 15,
          f"{n} queries")
    n = count_queries(lambda: client.get("/"))
    check(f"No N+1 on / (queries={n})", n < 15, f"{n} queries")

    print(f"\n=== {PASS} passed, {FAIL} failed ===\n")
    sys.exit(1 if FAIL else 0)
