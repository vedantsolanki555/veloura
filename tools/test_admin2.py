"""Feature 2 tests: admin categories + products.

Covers:
- Category add / edit / delete rules (blocked while it has products), unique slug
- Product create with 3 images + 3 variants, edit, inactive hides from /shop
- Delete rules: soft (has orders) vs hard (no orders)
- Invalid upload (wrong type, too big), duplicate variant, discount >= price
- Products list search / filters / pagination
"""

import io
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import (
    Category,
    Order,
    OrderItem,
    Product,
    ProductImage,
    ProductVariant,
    User,
)
from app.utils import slugify, unique_slug

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


def png_bytes(size_kb=1):
    """Minimal valid PNG bytes (1x1 pixel), padded to roughly size_kb."""
    # Real 1x1 transparent PNG.
    base = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d4944415478da63f8ffff3f0300050201ff899a3d1e000000004945"
        "4e44ae426082"
    )
    if size_kb > 1:
        # Pad with a tEXt chunk-ish blob — still a valid PNG for our size check
        # (we only look at byte length, not decode it).
        base = base + b"\x00" * ((size_kb - 1) * 1024)
    return base


def file_tuple(name="test.png", size_kb=1):
    """(BytesIO, filename, content_type) — the format Werkzeug's test client
    expects for one uploaded file."""
    return (io.BytesIO(png_bytes(size_kb)), name, "image/png")


with app.app_context():
    db.create_all()

    # Clean leftovers from earlier runs. Delete images/variants/orders FIRST,
    # then products — bulk .delete() bypasses ORM cascades, so doing it the
    # other way leaves orphan rows that later reuse product ids.
    old_products = Product.query.filter(
        db.or_(
            Product.name.like("Test Product%"),
            Product.slug.like("test-product%"),
        )
    ).all()
    old_ids = [p.id for p in old_products]
    if old_ids:
        ProductImage.query.filter(ProductImage.product_id.in_(old_ids)).delete(
            synchronize_session=False)
        ProductVariant.query.filter(ProductVariant.product_id.in_(old_ids)).delete(
            synchronize_session=False)
        OrderItem.query.filter(OrderItem.product_id.in_(old_ids)).delete(
            synchronize_session=False)
        Product.query.filter(Product.id.in_(old_ids)).delete(
            synchronize_session=False)
    Category.query.filter(Category.name.in_(
        ["TestCat", "TestCat2", "TestCat Empty", "RenamedCat"]
    )).delete(synchronize_session=False)
    Order.query.filter(Order.customer_name == "Test Customer").delete(
        synchronize_session=False)
    db.session.commit()

    client = app.test_client()
    print("\n=== Feature 2: Admin categories + products ===\n")

    # Admin login (session-based, no CSRF needed for login here since we
    # fetch the token anyway).
    login_admin(client)

    # ============================================================
    # CATEGORIES
    # ============================================================

    # --- 1. Add category ---
    r = client.get("/admin/categories")
    check("GET /admin/categories returns 200", r.status_code == 200)
    csrf = extract_csrf(r.data)
    r = client.post("/admin/categories", data={
        "csrf_token": csrf, "name": "TestCat",
    }, follow_redirects=True)
    cat = Category.query.filter_by(name="TestCat").first()
    check("POST adds category", cat is not None)
    check("Category slug auto-generated", cat is not None and cat.slug == "testcat")

    # --- 2. Duplicate name rejected ---
    csrf = extract_csrf(client.get("/admin/categories").data)
    r = client.post("/admin/categories", data={
        "csrf_token": csrf, "name": "TestCat",
    }, follow_redirects=True)
    check("Duplicate category name rejected", b"already exists" in r.data)

    # --- 3. Same name different case rejected ---
    csrf = extract_csrf(client.get("/admin/categories").data)
    r = client.post("/admin/categories", data={
        "csrf_token": csrf, "name": "testcat",
    }, follow_redirects=True)
    check("Duplicate category (case-insensitive) rejected", b"already exists" in r.data)

    # --- 4. Unique slug when names collide after slugify ---
    csrf = extract_csrf(client.get("/admin/categories").data)
    client.post("/admin/categories", data={"csrf_token": csrf, "name": "TestCat 2"})
    cat2 = Category.query.filter_by(name="TestCat 2").first()
    check("Slug collision gets -2 suffix",
          cat2 is not None and cat2.slug == "testcat-2",
          f"(got {cat2.slug if cat2 else None})")

    # --- 5. Empty category can be deleted ---
    csrf = extract_csrf(client.get("/admin/categories").data)
    empty = Category(name="TestCat Empty", slug="testcat-empty")
    db.session.add(empty)
    db.session.commit()
    csrf = extract_csrf(client.get("/admin/categories").data)
    client.post(f"/admin/categories/{empty.id}/delete", data={"csrf_token": csrf})
    check("Empty category deletes",
          db.session.get(Category, empty.id) is None)

    # --- 6. Category with products cannot be deleted ---
    product = Product(
        name="Test Product Alpha",
        slug="test-product-alpha",
        description="A test product.",
        fabric_care="Machine wash.",
        price=999,
        category_id=cat.id,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(ProductVariant(product=product, size="M", colour="Blue", stock=5))
    db.session.commit()

    csrf = extract_csrf(client.get("/admin/categories").data)
    r = client.post(f"/admin/categories/{cat.id}/delete", data={"csrf_token": csrf},
                    follow_redirects=True)
    check("Category with products refuses delete",
          db.session.get(Category, cat.id) is not None
          and b"Cannot delete" in r.data)

    # --- 7. Edit category ---
    csrf = extract_csrf(client.get(f"/admin/categories/{cat.id}/edit").data)
    r = client.post(f"/admin/categories/{cat.id}/edit", data={
        "csrf_token": csrf, "name": "RenamedCat",
    }, follow_redirects=True)
    db.session.expire_all()
    cat = db.session.get(Category, cat.id)
    check("Category rename works", cat.name == "RenamedCat")
    check("Category slug unchanged after rename", cat.slug == "testcat")

    # ============================================================
    # PRODUCTS
    # ============================================================

    # --- 8. Create product with 3 variants + 3 images ---
    r = client.get("/admin/products/new")
    check("GET /admin/products/new returns 200", r.status_code == 200)
    csrf = extract_csrf(r.data)

    data = {
        "csrf_token": csrf,
        "name": "Test Product Beta",
        "slug": "",
        "category_id": str(cat.id),
        "description": "Lovely test product.",
        "fabric_care": "Dry clean only.",
        "price": "1500",
        "discount_price": "1200",
        "is_featured": "y",
        "is_new": "y",
        "is_active": "y",
        "variant_id": ["", "", ""],
        "variant_size": ["S", "M", "L"],
        "variant_colour": ["Indigo", "Indigo", "Black"],
        "variant_stock": ["4", "6", "2"],
        "images": [
            file_tuple("one.png"),
            file_tuple("two.png"),
            file_tuple("three.png"),
        ],
    }
    r = client.post("/admin/products/new", data=data,
                    follow_redirects=True)
    beta = Product.query.filter_by(name="Test Product Beta").first()
    check("POST creates product", beta is not None)
    check("Product slug auto-generated",
          beta is not None and beta.slug == "test-product-beta")
    if beta:
        check("3 variants created", len(beta.variants) == 3,
              f"(got {len(beta.variants)})")
        check("3 images uploaded", len(beta.images) == 3,
              f"(got {len(beta.images)})")
        check("Images have positions 0,1,2",
              sorted(i.position for i in beta.images) == [0, 1, 2])
        check("Local upload URL stored",
              all(i.image_url.startswith("/static/uploads/") for i in beta.images))

    # --- 9. Duplicate variant rejected ---
    csrf = extract_csrf(client.get("/admin/products/new").data)
    r = client.post("/admin/products/new", data={
        "csrf_token": csrf,
        "name": "Test Product Dup",
        "category_id": str(cat.id),
        "price": "500",
        "variant_id": ["", ""],
        "variant_size": ["M", "M"],
        "variant_colour": ["Red", "red"],
        "variant_stock": ["1", "2"],
    }, follow_redirects=True)
    check("Duplicate size+colour rejected",
          b"duplicate size" in r.data.lower()
          and Product.query.filter_by(name="Test Product Dup").first() is None)

    # --- 10. Discount >= price rejected ---
    csrf = extract_csrf(client.get("/admin/products/new").data)
    r = client.post("/admin/products/new", data={
        "csrf_token": csrf,
        "name": "Test Product BadPrice",
        "category_id": str(cat.id),
        "price": "500",
        "discount_price": "600",
        "variant_id": [""],
        "variant_size": ["M"],
        "variant_colour": ["Red"],
        "variant_stock": ["1"],
    }, follow_redirects=True)
    check("Discount >= price rejected",
          b"lower than the full price" in r.data
          and Product.query.filter_by(name="Test Product BadPrice").first() is None)

    # --- 11. Negative stock rejected ---
    csrf = extract_csrf(client.get("/admin/products/new").data)
    r = client.post("/admin/products/new", data={
        "csrf_token": csrf,
        "name": "Test Product NegStock",
        "category_id": str(cat.id),
        "price": "500",
        "variant_id": [""],
        "variant_size": ["M"],
        "variant_colour": ["Red"],
        "variant_stock": ["-2"],
    }, follow_redirects=True)
    check("Negative stock rejected",
          Product.query.filter_by(name="Test Product NegStock").first() is None)

    # --- 12. Invalid file type rejected ---
    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    r = client.post(f"/admin/products/{beta.id}/images",
                    data={
                        "csrf_token": csrf,
                        "images": (io.BytesIO(b"MZ not an image"), "evil.exe",
                                   "application/octet-stream"),
                    },
                    follow_redirects=True)
    db.session.expire_all()
    beta = db.session.get(Product, beta.id)
    check("Non-image file rejected",
          b"not allowed" in r.data and len(beta.images) == 3)

    # --- 13. File > 5 MB rejected ---
    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    r = client.post(f"/admin/products/{beta.id}/images",
                    data={
                        "csrf_token": csrf,
                        "images": file_tuple("big.png", size_kb=6 * 1024),  # ~6 MB
                    },
                    follow_redirects=True)
    db.session.expire_all()
    beta = db.session.get(Product, beta.id)
    check("File over 5 MB rejected", b"maximum is 5 MB" in r.data
          and len(beta.images) == 3)

    # --- 14. Edit product: change price + one variant stock ---
    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    variant_ids = [str(v.id) for v in beta.variants]
    sizes = [v.size for v in beta.variants]
    colours = [v.colour for v in beta.variants]
    stocks = ["4", "10", "2"]  # M goes from 6 -> 10
    r = client.post(f"/admin/products/{beta.id}/edit", data={
        "csrf_token": csrf,
        "name": "Test Product Beta",
        "slug": beta.slug,
        "category_id": str(cat.id),
        "description": "Updated description.",
        "fabric_care": "Dry clean only.",
        "price": "1600",
        "discount_price": "1200",
        "is_active": "y",
        "variant_id": variant_ids,
        "variant_size": sizes,
        "variant_colour": colours,
        "variant_stock": stocks,
    }, follow_redirects=True)
    db.session.expire_all()
    beta = db.session.get(Product, beta.id)
    check("Edit updates price", float(beta.price) == 1600.0)
    m_variant = next(v for v in beta.variants if v.size == "M")
    check("Edit updates variant stock", m_variant.stock == 10)

    # --- 15. Removing a variant row deletes it ---
    r = client.post(f"/admin/products/{beta.id}/edit", data={
        "csrf_token": csrf,
        "name": "Test Product Beta",
        "slug": beta.slug,
        "category_id": str(cat.id),
        "price": "1600",
        "discount_price": "1200",
        "is_active": "y",
        "variant_id": [variant_ids[0], variant_ids[1]],  # L row removed
        "variant_size": [sizes[0], sizes[1]],
        "variant_colour": [colours[0], colours[1]],
        "variant_stock": ["4", "10"],
    }, follow_redirects=True)
    db.session.expire_all()
    beta = db.session.get(Product, beta.id)
    check("Removed variant row deleted", len(beta.variants) == 2,
          f"(got {len(beta.variants)})")

    # --- 16. Make image main + move + delete ---
    images = sorted(beta.images, key=lambda i: i.position)
    second_id = images[1].id
    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    client.post(f"/admin/images/{second_id}/main", data={"csrf_token": csrf})
    db.session.expire_all()
    images = sorted(db.session.get(Product, beta.id).images, key=lambda i: i.position)
    check("Make main sets position 0", images[0].id == second_id)

    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    first_id = images[0].id
    client.post(f"/admin/images/{first_id}/move",
                data={"csrf_token": csrf, "direction": "right"})
    db.session.expire_all()
    images = sorted(db.session.get(Product, beta.id).images, key=lambda i: i.position)
    check("Move right swaps order", images[1].id == first_id)

    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    deleted_image_id = images[2].id
    client.post(f"/admin/images/{deleted_image_id}/delete", data={"csrf_token": csrf})
    db.session.expire_all()
    beta = db.session.get(Product, beta.id)
    check("Delete image removes row", len(beta.images) == 2)
    check("Remaining positions renumbered",
          sorted(i.position for i in beta.images) == [0, 1])

    # --- 17. Inactive product disappears from /shop ---
    csrf = extract_csrf(client.get(f"/admin/products/{beta.id}/edit").data)
    variant_ids = [str(v.id) for v in beta.variants]
    client.post(f"/admin/products/{beta.id}/edit", data={
        "csrf_token": csrf,
        "name": "Test Product Beta",
        "slug": beta.slug,
        "category_id": str(cat.id),
        "price": "1600",
        "is_active": "",          # unchecked = inactive
        "variant_id": variant_ids,
        "variant_size": [v.size for v in beta.variants],
        "variant_colour": [v.colour for v in beta.variants],
        "variant_stock": [str(v.stock) for v in beta.variants],
    }, follow_redirects=True)
    db.session.expire_all()
    beta = db.session.get(Product, beta.id)
    check("Inactive flag saved", beta.is_active is False)
    r = client.get("/shop")
    check("Inactive product hidden from /shop", b"Test Product Beta" not in r.data)
    r = client.get(f"/product/{beta.id}")
    check("Inactive product 404 on detail page", r.status_code == 404)

    # reactivate for the next checks
    beta.is_active = True
    db.session.commit()

    # --- 18. Products list: search + filter + pagination ---
    r = client.get("/admin/products?q=Test+Product+Beta")
    check("Search finds product", b"Test Product Beta" in r.data)

    r = client.get(f"/admin/products?category={cat.id}")
    check("Category filter works", b"Test Product Beta" in r.data)

    r = client.get("/admin/products?stock=out")
    check("Stock filter: out-of-stock runs without error", r.status_code == 200)

    # Create enough products to cross the 20-per-page line.
    for i in range(25):
        db.session.add(Product(
            name=f"Test Product Bulk {i:02d}",
            slug=f"test-product-bulk-{i:02d}",
            price=100 + i,
            category_id=cat.id,
        ))
    db.session.commit()
    r = client.get("/admin/products?q=Test+Product+Bulk")
    html = r.data.decode("utf-8")
    check("Pagination shows page 1 of 2", "Page 1 / 2" in html)
    r = client.get("/admin/products?q=Test+Product+Bulk&page=2")
    check("Page 2 loads", r.status_code == 200)

    # --- 19. Soft delete: product with orders stays (inactive) ---
    # Attach a fake order item to alpha.
    alpha = Product.query.filter_by(slug="test-product-alpha").first()
    order = Order(
        customer_name="Test Customer",
        phone="9876543210",
        address="1 Test Street",
        city="Mumbai",
        pincode="400001",
        status="New",
        total=999,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(OrderItem(
        order=order, product=alpha, quantity=1, price=999,
    ))
    db.session.commit()

    csrf = extract_csrf(client.get(f"/admin/products/{alpha.id}/edit").data)
    r = client.post(f"/admin/products/{alpha.id}/delete", data={"csrf_token": csrf},
                    follow_redirects=True)
    db.session.expire_all()
    alpha = db.session.get(Product, alpha.id)
    check("Product with orders: soft delete (inactive, row kept)",
          alpha is not None and alpha.is_active is False)

    # --- 20. Hard delete: product without orders is removed ---
    bulk0 = Product.query.filter_by(slug="test-product-bulk-00").first()
    csrf = extract_csrf(client.get(f"/admin/products/{bulk0.id}/edit").data)
    client.post(f"/admin/products/{bulk0.id}/delete", data={"csrf_token": csrf})
    check("Product without orders: hard delete",
          db.session.get(Product, bulk0.id) is None)

    # --- 21. Normal customer gets 403 on all admin product/category pages ---
    logout(client)
    r = client.get("/register")
    csrf = extract_csrf(r.data)
    client.post("/register", data={
        "csrf_token": csrf, "name": "Shop Customer",
        "email": "test-admin2-customer@example.com",
        "phone": "9876543211", "password": "secret123", "confirm": "secret123",
    }, follow_redirects=True)
    for path in ["/admin/products", "/admin/products/new", "/admin/categories"]:
        r = client.get(path, follow_redirects=False)
        check(f"Customer {path} gets 403", r.status_code == 403)
    logout(client)

    # --- 22. Slug helpers ---
    check("slugify basic", slugify("Men's Silk Kurta!") == "mens-silk-kurta")
    check("slugify unicode stripped", slugify("!!!") == "")

    # --- cleanup ---
    leftover = Product.query.filter(
        db.or_(Product.name.like("Test Product%"),
               Product.slug.like("test-product%"))
    ).all()
    leftover_ids = [p.id for p in leftover]
    if leftover_ids:
        ProductImage.query.filter(ProductImage.product_id.in_(leftover_ids)).delete(
            synchronize_session=False)
        ProductVariant.query.filter(
            ProductVariant.product_id.in_(leftover_ids)
        ).delete(synchronize_session=False)
        OrderItem.query.filter(OrderItem.product_id.in_(leftover_ids)).delete(
            synchronize_session=False)
        Product.query.filter(Product.id.in_(leftover_ids)).delete(
            synchronize_session=False)
    Category.query.filter(Category.name.in_(
        ["RenamedCat", "TestCat 2"]
    )).delete(synchronize_session=False)
    Order.query.filter(Order.customer_name == "Test Customer").delete(
        synchronize_session=False)
    db.session.commit()
    User.query.filter(User.email.like("test-admin2-%")).delete()
    db.session.commit()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
