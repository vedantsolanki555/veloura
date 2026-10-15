"""
Seed the database with sample data.

Creates:
- 1 admin user
- 4 categories (Men, Women, Kids, Accessories)
- 18 products, each with images and size/colour variants

Run:  python seed.py

Safe to re-run: if an admin user already exists, it exits without touching data.
"""

from app import create_app, db
from app.models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
    User,
)

# Placeholder images. Real product photos replace these in a later step.
PLACEHOLDER = "https://placehold.co/600x800?text=Veloura"


def img(name):
    """Build a placeholder image URL that says the product name."""
    return f"https://placehold.co/600x800?text={name.replace(' ', '+')}"


# (name, slug, description, price, discount_price, fabric_care, is_featured, is_new)
# price/discount_price: discount_price None = not on sale.
PRODUCTS = [
    # --- Men ---
    ("Men's Silk Kurta", "mens-silk-kurta",
     "Elegant silk kurta for festive occasions. Soft hand-feel with a subtle sheen.",
     2499, None, "Dry clean only. Iron on low heat, inside out.", True, False),
    ("Men's Linen Shirt", "mens-linen-shirt",
     "Breathable pure linen shirt. Perfect for warm days and smart-casual evenings.",
     1599, 1299, "Machine wash cold, gentle cycle. Do not bleach.", True, True),
    ("Men's Cotton Chinos", "mens-cotton-chinos",
     "Slim-fit stretch chinos in stone cotton twill. Office to weekend.",
     1799, None, "Machine wash cold. Tumble dry low.", False, True),
    ("Men's Nehru Jacket", "mens-nehru-jacket",
     "Textured Nehru jacket with a modern cut. Pairs with kurta or shirt.",
     2999, 2399, "Dry clean only.", True, False),
    ("Men's Polo T-Shirt", "mens-polo-tshirt",
     "Classic pique polo in pima cotton. Ribbed collar and two-button placket.",
     999, None, "Machine wash cold. Do not iron print.", False, False),

    # --- Women ---
    ("Women's Chiffon Saree", "womens-chiffon-saree",
     "Flowy chiffon saree with embroidered border. Comes with unstitched blouse piece.",
     3499, 2999, "Dry clean only. Store folded in muslin.", True, True),
    ("Women's Anarkali Suit", "womens-anarkali-suit",
     "Floor-length Anarkali with dupatta. Georgette with sequin work.",
     4299, None, "Dry clean only.", True, False),
    ("Women's Cotton Kurti", "womens-cotton-kurti",
     "Everyday straight-cut kurti in soft cotton with side slits.",
     899, 699, "Machine wash cold. Do not bleach.", False, True),
    ("Women's Palazzo Pants", "womens-palazzo-pants",
     "High-waist palazzos in crepe. Wide leg, elastic back.",
     1199, None, "Machine wash cold. Hang dry.", False, False),
    ("Women's Silk Blend Lehenga", "womens-silk-blend-lehenga",
     "Festive lehenga with heavy zari work. Semi-stitched, with dupatta.",
     5999, 4999, "Dry clean only.", True, True),
    ("Women's Denim Jacket", "womens-denim-jacket",
     "Cropped denim jacket with distressed finish. Layer over anything.",
     1899, None, "Machine wash cold, inside out.", False, False),

    # --- Kids ---
    ("Kids' Cotton Frock", "kids-cotton-frock",
     "Twirl-ready frock in soft cotton with puff sleeves. Ages 2-8.",
     799, 599, "Machine wash cold. Do not tumble dry.", False, True),
    ("Kids' Graphic Tee", "kids-graphic-tee",
     "Fun printed tee in 100% cotton. Pre-shrunk fit.",
     499, None, "Machine wash warm. Do not iron on print.", False, False),
    ("Kids' Chinos Shorts", "kids-chinos-shorts",
     "Elastic-waist chino shorts. Durable twill for playground days.",
     649, 549, "Machine wash cold. Tumble dry low.", False, True),
    ("Kids' Festive Kurta Set", "kids-festive-kurta-set",
     "Kurta and pyjama set in silk blend. Ready for family functions.",
     1299, None, "Dry clean only.", True, False),

    # --- Accessories ---
    ("Silk Pocket Square", "silk-pocket-square",
     "Hand-rolled silk pocket square. The finishing touch for a suit.",
     499, None, "Dry clean only.", False, False),
    ("Leather Belt", "leather-belt",
     "Full-grain leather belt with brushed buckle. Reversible black/brown.",
     1199, 999, "Wipe clean. Condition leather occasionally.", False, True),
    ("Cotton Stole", "cotton-stole",
     "Lightweight cotton stole with fringe. Year-round layering piece.",
     799, None, "Hand wash cold. Dry flat.", False, False),
]


def seed():
    """Insert sample data. Does nothing if data already exists."""

    app = create_app()

    with app.app_context():
        # Create tables if missing (e.g. brand new database).
        db.create_all()

        # Idempotency guard: if admin already exists, assume data is seeded.
        if User.query.filter_by(email="admin@veloura.local").first():
            print("Database already seeded — nothing to do.")
            return

        # 1) Admin user.
        # NOTE: this password is only for local sample data.
        # Change it before deploying, or better: set it from an env var.
        admin = User(email="admin@veloura.local", is_admin=True)
        admin.set_password("admin123")
        db.session.add(admin)

        # 2) Categories.
        categories = {}
        for name, slug in [
            ("Men", "men"),
            ("Women", "women"),
            ("Kids", "kids"),
            ("Accessories", "accessories"),
        ]:
            cat = Category(name=name, slug=slug)
            db.session.add(cat)
            categories[slug] = cat

        # Flush writes the categories to the DB so they get IDs we can use.
        db.session.flush()

        # 3) Products + images + variants.
        for (
            name, slug, description, price, discount_price,
            fabric_care, is_featured, is_new,
        ) in PRODUCTS:
            # Pick category from the slug prefix (mens-..., womens-..., ...).
            if slug.startswith("mens"):
                cat = categories["men"]
            elif slug.startswith("womens"):
                cat = categories["women"]
            elif slug.startswith("kids"):
                cat = categories["kids"]
            else:
                cat = categories["accessories"]

            product = Product(
                name=name,
                slug=slug,
                description=description,
                price=price,
                discount_price=discount_price,
                fabric_care=fabric_care,
                is_featured=is_featured,
                is_new=is_new,
                category=cat,
            )
            db.session.add(product)

            # Two placeholder images per product (front/back placeholders).
            product.images.append(ProductImage(image_url=img(name), position=0))
            product.images.append(ProductImage(image_url=PLACEHOLDER, position=1))

            # Size/colour variants. Accessories use "Free" size.
            if cat.slug == "accessories":
                combos = [("Free", "Black"), ("Free", "Brown")]
            elif cat.slug == "kids":
                combos = [("2-3Y", "Ivory"), ("4-5Y", "Blue"), ("6-7Y", "Rose")]
            else:
                combos = [
                    ("S", "Indigo"),
                    ("M", "Indigo"),
                    ("L", "Black"),
                    ("XL", "Black"),
                ]

            for size, colour in combos:
                product.variants.append(
                    ProductVariant(size=size, colour=colour, stock=10)
                )

        # One transaction: all rows commit together or not at all.
        db.session.commit()

        # Print a short report.
        print("Seeded successfully!")
        print(f"  Users:      {User.query.count()}")
        print(f"  Categories: {Category.query.count()}")
        print(f"  Products:   {Product.query.count()}")
        print(f"  Images:     {ProductImage.query.count()}")
        print(f"  Variants:   {ProductVariant.query.count()}")


if __name__ == "__main__":
    seed()
