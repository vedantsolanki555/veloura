#!/usr/bin/env python
"""Step 3 verification (item 14).

Run the dev server first, then:
    python tools/check_step3.py

Covers checklist items 1-13 over HTTP + local files.
"""
import html as html_lib
import json
import os
import re
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):        # Windows console: print ₹ etc.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("VELA_URL", "http://127.0.0.1:5000")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

failures = []
passes = 0


def check(name, condition, detail=""):
    global passes
    if condition:
        passes += 1
        print(f"  PASS  {name}")
    else:
        failures.append(name)
        print(f"  FAIL  {name}  {detail}")


def get(path):
    """Return (status_code, html_text)."""
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace")


def img_tags(html):
    """All <img> tags as dicts of attributes."""
    out = []
    for tag in re.findall(r"<img[^>]*>", html, re.S):
        out.append(dict(re.findall(r'([\w-]+)="([^"]*)"', tag)))
    return out


def button_tag(html, attr, value):
    """The full <button> tag that carries data-<attr>="<value>"."""
    match = re.search(rf'<button[^>]*data-{attr}="{re.escape(value)}"[^>]*>', html, re.S)
    return match.group(0) if match else None


def variants_of(page):
    """Parse the embedded data-variants JSON (HTML-escaped in the source)."""
    match = re.search(r'id="pd-layout"[^>]*data-variants="([^"]*)"', page, re.S)
    if not match:
        return []
    try:
        return json.loads(html_lib.unescape(match.group(1)))
    except Exception:  # noqa: BLE001
        return []


def product_cards(html):
    """[(title, effective_price)] in page order."""
    cards = []
    for block in re.findall(r'<article class="product-card">.*?</article>', html, re.S):
        title_match = re.search(r'<h3 class="card-title">\s*<a[^>]*>([^<]+)</a>', block, re.S)
        sale = re.search(r'<span class="sale">\s*₹([\d,]+)', block)
        plain = re.search(r'<span>\s*₹([\d,]+)', block)
        money = sale or plain
        cards.append((
            title_match.group(1).strip() if title_match else "?",
            int(money.group(1).replace(",", "")) if money else -1,
        ))
    return cards


def local_path(static_url):
    return os.path.join(ROOT, "app", static_url.lstrip("/"))


# ---------------------------------------------------------------- images (13)
print("\n[13] Local images + credits")
sys.path.insert(0, ROOT)
from app.images import CATEGORY_IMAGES, MODEL_IMAGES, PRODUCT_IMAGES  # noqa: E402

from app import create_app  # noqa: E402
from app.models import Product  # noqa: E402
from sqlalchemy import or_  # noqa: E402

app = create_app()

all_images = [
    (slug, img["src"], img["alt"])
    for slug, images in PRODUCT_IMAGES.items()
    for img in images
] + [
    ("home:" + key, value, "")
    for key, value in list(CATEGORY_IMAGES.items()) + list(MODEL_IMAGES.items())
]

missing, too_big, no_alt = [], [], []
for slug, src, alt in all_images:
    path = local_path(src)
    if not os.path.isfile(path):
        missing.append(src)
        continue
    if os.path.getsize(path) >= 300_000:
        too_big.append(f"{src} ({os.path.getsize(path)} B)")
    if src.startswith("/static/img/products/") and not alt.strip():
        no_alt.append(src)

check("every image file exists on disk", not missing, str(missing[:3]))
check("every image < 300 KB", not too_big, str(too_big[:3]))
check("every product image has alt text", not no_alt, str(no_alt[:3]))

credits_path = os.path.join(ROOT, "app", "static", "img", "products", "CREDITS.md")
credits = open(credits_path, encoding="utf-8").read() if os.path.isfile(credits_path) else ""
product_files = [src.split("/")[-1] for slug, src, alt in all_images if "/img/products/" in src]
uncredited = [f for f in product_files if f not in credits]
check("CREDITS.md lists every product photo", bool(credits) and not uncredited, str(uncredited[:3]))

manifest_path = os.path.join(ROOT, "app", "static", "img", "products", "manifest.json")
try:
    manifest_ok = isinstance(json.load(open(manifest_path, encoding="utf-8")), (list, dict))
except Exception as exc:  # noqa: BLE001
    manifest_ok = False
    print("    manifest error:", exc)
check("manifest.json parses", manifest_ok)

# ------------------------------------------------------------------ home (9)
print("\n[1/6/9/10] Home page")
status, home = get("/")
check("GET / → 200", status == 200, status)
check("font = Cormorant Garamond", "Cormorant+Garamond" in home)
check("font = Jost", "Jost" in home)
check("old fonts gone", "Playfair" not in home and "Inter" not in home)
check("navbar Login link removed", 'nav-login' not in home)
meta = re.findall(r'<meta name="description" content="([^"]{20,400})"', home)
check("home meta description present", len(meta) == 1, meta)
home_imgs = [t for t in img_tags(home) if t.get("src", "").startswith("/static/img/home/")]
check("home uses 6 local images", len(home_imgs) == 6, len(home_imgs))
check("home images have alt text", all(t.get("alt", "").strip() for t in home_imgs))
check(
    "prices formatted ₹1,199 (no decimals)",
    bool(re.search(r"₹\d{1,3}(?:,\d{2,3})+", home)) and ".00" not in home,
)

# ---------------------------------------------------------------- shop (7,8)
print("\n[7/8/9] Shop sorting, filters, search")
status, asc = get("/shop?sort=price_asc")
asc_cards = product_cards(asc)
asc_prices = [p for _, p in asc_cards]
check("sort price_asc works", status == 200 and len(asc_cards) >= 10, len(asc_cards))
check("price_asc is really sorted", asc_prices == sorted(asc_prices), asc_prices[:6])

status, desc = get("/shop?sort=price_desc")
desc_prices = [p for _, p in product_cards(desc)]
check("price_desc is really sorted", desc_prices == sorted(desc_prices, reverse=True), desc_prices[:6])

status, cheap_first = get("/shop?sort=price_asc")
first_title, first_price = product_cards(cheap_first)[0]
check("cheapest = ₹499 item", first_price == 499, f"{first_title} @{first_price}")

status, filtered = get("/shop?min=3000&sort=price_asc")
filtered_prices = [p for _, p in product_cards(filtered)]
check("min=3000 filter applied", filtered_prices and min(filtered_prices) >= 3000, filtered_prices[:6])
check("nav search keeps min filter", 'name="min" value="3000"' in filtered)

status, searched = get("/shop?q=kurta")
search_titles = {html_lib.unescape(t) for t, _ in product_cards(searched)}
with app.app_context():
    expected_titles = {
        p.name
        for p in Product.query.filter(
            or_(Product.name.ilike("%kurta%"), Product.description.ilike("%kurta%"))
        ).all()
    }
check("search q=kurta returns exactly the DB matches",
      search_titles == expected_titles,
      f"extra={sorted(search_titles - expected_titles)} missing={sorted(expected_titles - search_titles)}")

status, men = get("/shop/men?min=2000&sort=price_asc&secret=x")
check("category page keeps filters in nav form",
      'action="/shop/men"' in men and 'name="min" value="2000"' in men and 'name="sort" value="price_asc"' in men)
check("shop meta description present", len(re.findall(r'<meta name="description" content="([^"]{20,400})"', asc)) == 1)
check("category page meta description present",
      len(re.findall(r'<meta name="description" content="([^"]{20,400})"', men)) == 1)

# ------------------------------------------------------------ product (1-5,6)
print("\n[1/2/3/4/5/6] Product detail page")
status, pd = get("/product/1")
check("GET /product/1 → 200", status == 200, status)

thumbs = re.findall(r'<button[^>]*class="pd-thumb[^"]*"[^>]*>', pd, re.S)
check("gallery has clickable thumbnails (>=2)", len(thumbs) >= 2, len(thumbs))
check("thumbnails carry data-full + data-alt",
      all('data-full="/static/img/products/' in t and 'data-alt="' in t for t in thumbs))
check("thumbnail scroll container present", 'id="pd-thumbs"' in pd and 'id="pd-main-wrap"' in pd)
check("main image alt is descriptive", len(re.search(r'id="pd-main-img"[^>]*alt="([^"]+)"', pd, re.S).group(1)) >= 15)

colour_btns = re.findall(r'<button[^>]*class="colour-btn[^"]*"[^>]*>', pd, re.S)
check("colour swatch buttons present", len(colour_btns) >= 1, len(colour_btns))
check("swatch has inline hex colour",
      re.search(r'class="swatch" style="background: #[0-9a-fA-F]{3,8}"', pd) is not None)
size_btns = re.findall(r'<button[^>]*class="size-btn[^"]*"[^>]*>', pd, re.S)
check("size buttons present", len(size_btns) >= 3, len(size_btns))

variants_raw = re.search(r'id="pd-layout"[^>]*data-variants="([^"]*)"', pd, re.S)
variants = variants_of(pd)
check("variants JSON embedded + parses",
      variants_raw is not None and isinstance(variants, list) and variants
      and {"size", "colour", "stock"} <= set(variants[0]),
      f"n={len(variants)}")

add_tag = re.search(r'<button[^>]*id="add-to-cart-btn"[^>]*>', pd, re.S).group(0)
wa_tag = re.search(r'<button[^>]*id="whatsapp-btn"[^>]*>', pd, re.S).group(0)
check("Add to Cart starts disabled", "disabled" in add_tag)
check("WhatsApp button starts enabled (number set)", "disabled" not in wa_tag)
check("WhatsApp number from env in data-whatsapp", 'data-whatsapp="919876543210"' in pd)

check("price shows ₹2,499 (inr filter)", "₹2,499" in pd and ".00" not in pd)
check("'Cart is coming soon' message present", "Cart is coming soon" in pd)
check("stock line asks to select size+colour", "Select size and colour to check stock" in pd)
check("qty input max set server-side", re.search(r'id="qty-input"[^>]*max="\d+"', pd, re.S) is not None)
check("product meta description present",
      len(re.findall(r'<meta name="description" content="([^"]{20,400})"', pd)) == 1)
check("related products section", "You may also like" in pd)

# --------------------------------------------------- stock fixtures (item 11)
print("\n[11] Stock fixtures")
status, chinos = get("/product/3")
chinos_vars = variants_of(chinos)
m_var = next((v for v in chinos_vars if v["size"] == "M"), None)
m_tag = button_tag(chinos, "size", "M")
l_tag = next((button_tag(chinos, "size", s) for s in ("L", "XL") if button_tag(chinos, "size", s)), None)
check("chinos M variant stock = 0", m_var is not None and m_var["stock"] == 0, m_var)
check("chinos M size button disabled", m_tag and "disabled" in m_tag)
check("chinos has an in-stock size enabled", l_tag and "disabled" not in l_tag)

status, tee = get("/product/13")
check("graphic tee page → 200", status == 200, status)
check("graphic tee shows Out of stock", "Out of stock" in tee)
tee_sizes = re.findall(r'<button[^>]*class="size-btn[^"]*"[^>]*>', tee, re.S)
check("graphic tee all sizes disabled", tee_sizes and all("disabled" in s for s in tee_sizes),
      [s for s in tee_sizes if "disabled" not in s])
check("graphic tee action buttons disabled",
      "disabled" in re.search(r'<button[^>]*id="add-to-cart-btn"[^>]*>', tee, re.S).group(0)
      and "disabled" in re.search(r'<button[^>]*id="whatsapp-btn"[^>]*>', tee, re.S).group(0))
check("graphic tee Out of Stock badge", "pd-oos-badge" in tee)

# ----------------------------------------------------------------- misc (12)
print("\n[9/12] Meta + docs + 404")
status, missing_page = get("/this-page-does-not-exist")
check("custom 404 page status 404", status == 404, status)
check("404 shows 'Page not found' + Back to Shop", "Page not found" in missing_page and "Back to Shop" in missing_page)

map_path = os.path.join(ROOT, "docs", "PROJECT_MAP.md")
map_text = open(map_path, encoding="utf-8").read() if os.path.isfile(map_path) else ""
check("PROJECT_MAP.md exists + Step 3 checklist marked Done",
      map_text.count("**Done**") >= 14, map_text.count("**Done**"))
check("PROJECT_MAP no longer claims old phase numbering",
      "Customer login/signup nahi hai" in map_text)

status, static_resp = get("/static/img/products/mens-silk-kurta-1.jpg")
check("static product photo serves 200", status == 200, status)

env_text = open(os.path.join(ROOT, ".env.example"), encoding="utf-8").read()
check(".env.example documents WHATSAPP_NUMBER", "WHATSAPP_NUMBER" in env_text)

# --------------------------------------------------------------------- done
print(f"\n{passes} passed, {len(failures)} failed")
if failures:
    print("Failed:")
    for name in failures:
        print("  -", name)
    sys.exit(1)
print("ALL STEP 3 HTTP CHECKS PASSED")
