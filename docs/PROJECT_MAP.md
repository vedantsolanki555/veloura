# Veloura — Project Map

Is file me project ka pura naksha hai: kaunsi pages hain, kaunsi database tables hain.
Har naya phase aane par is file ko update karte raho.

---

## A) PAGE LIST

| Page | URL | Kaam | Phase | Status |
| --- | --- | --- | --- | --- |
| Home | `/` | Hero banner, featured, categories, new arrivals, Why Veloura | 2 | **Done** |
| Shop | `/shop` | Product grid, category filter, price filter, sort, search | 2 | **Done** |
| Category Shop | `/shop/<slug>` | Ek category ke products (men, women, kids, accessories) | 2 | **Done** |
| Product Detail | `/product/<id>` | Bada photo, size, quantity, related products | 3 | **Done** |
| Signup | `/signup` | Naya customer account banane ke liye | 4 | Baaki |
| Login | `/login` | Customer login | 4 | Baaki |
| Logout | `/logout` | Login band karna | 4 | Baaki |
| Cart | `/cart` | Customer ka shopping cart | 4 | Baaki |
| Checkout | `/checkout` | Address + order place karna | 5 | Baaki |
| My Orders | `/orders` | Customer ke apne orders ki list | 5 | Baaki |
| Admin Login | `/admin/login` | Sirf admin ke liye login | 6 | Baaki |
| Admin Products | `/admin/products` | Products add/edit/delete | 6 | Baaki |
| Admin Categories | `/admin/categories` | Categories add/edit/delete | 6 | Baaki |
| Admin Orders | `/admin/orders` | Orders dekhna + status update karna | 6 | Baaki |
| 404 | (koi bhi galat URL) | "Page not found" + Back to Shop button | 3 | **Done** |

---

## B) DATABASE TABLES

Database file (local dev): `instance/veloura.db`

### 1. users — customer aur admin dono ke accounts

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| email | String(120), unique | Login email |
| password_hash | String(256) | Password ka hash (plain text kabhi nahi) |
| is_admin | Boolean | `True` = admin, `False` = normal customer |
| created_at | DateTime | Account kab bana |

Links: `cart.user_id -> users.id`, `orders` se bhi future me
Abhi rows: **1** (sirf admin — `admin@veloura.local`)

### 2. categories — product groups (Men, Women, Kids, Accessories)

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| name | String(80), unique | Jaise "Men" |
| slug | String(80), unique | URL ke liye, jaise "men" (/shop/men) |

Links: `products.category_id -> categories.id`
Abhi rows: **4**

### 3. products — yahi asli "cloth" table hai (kapdon ki list)

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| name | String(200) | Product ka naam |
| slug | String(220), unique | URL-friendly naam (baad me use hoga) |
| description | Text | Product ki details |
| price | Numeric(10,2) | Original price (₹) |
| discount_price | Numeric(10,2), nullable | Sale price; NULL = no discount |
| fabric_care | Text | Fabric aur dhulne ka tarika |
| is_featured | Boolean | Home page "Featured" me dikhana hai? |
| is_new | Boolean | Home page "New Arrivals" me dikhana hai? |
| created_at | DateTime | Kab add hua |
| category_id | Integer (FK) | Kis category ka hai |

Links: `products.category_id -> categories.id`
Abhi rows: **18**

### 4. product_images — product ki photos (URLs)

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| image_url | String(500) | Photo ka URL (abhi placeholder) |
| position | Integer | Display order (0 = pehli photo) |
| product_id | Integer (FK) | Kis product ki photo |

Links: `product_images.product_id -> products.id`
Abhi rows: **36** (har product ki 2 photos)

### 5. product_variants — size / colour / stock

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| size | String(20) | S, M, L, XL, Free, 2-3Y etc. |
| colour | String(50) | Indigo, Black etc. |
| stock | Integer | Kitne piece available hain |
| product_id | Integer (FK) | Kis product ka variant |

Links: `product_variants.product_id -> products.id`
Abhi rows: **62**

### 6. cart — shopping cart (sirf table bani hai, logic Phase 4 me)

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| quantity | Integer | Kitne piece cart me |
| user_id | Integer (FK), nullable | Kis customer ka cart (NULL = guest) |
| product_id | Integer (FK) | Kaunsa product |
| variant_id | Integer (FK), nullable | Kaunsa size/colour |
| created_at | DateTime | Kab add kiya |

Links: `cart.user_id -> users.id`, `cart.product_id -> products.id`, `cart.variant_id -> product_variants.id`
Abhi rows: **0** (khaali table, Phase 4 me bharegi)

### 7. orders — customer ke orders

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| customer_name | String(120) | Naam |
| phone | String(20) | Phone number |
| address | Text | Pura address |
| city | String(80) | Shehar |
| pincode | String(10) | PIN code |
| notes | Text | Special instruction |
| status | String(20) | pending / confirmed / shipped / delivered / cancelled |
| total | Numeric(10,2) | Order ka total (₹) |
| created_at | DateTime | Order kab hua |

Links: (abhi koi FK nahi; Phase 5 me user_id add hoga)
Abhi rows: **0** (checkout baad me aayega)

### 8. order_items — order ke andar ek ek line (product)

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| quantity | Integer | Kitne piece |
| price | Numeric(10,2) | Order waqt ka price |
| order_id | Integer (FK) | Kis order ka |
| product_id | Integer (FK) | Kaunsa product |
| variant_id | Integer (FK), nullable | Kaunsa size/colour |

Links: `order_items.order_id -> orders.id`, `order_items.product_id -> products.id`
Abhi rows: **0**

---

## Quick notes

- **Admin login (abhi):** `admin@veloura.local` / `admin123` — production se pehle change karna zaroori hai.
- **Local dev server:** `python wsgi.py` → http://127.0.0.1:5000/
- **Seed data wapas chahiye?** `instance/veloura.db` delete karo, phir `python seed.py` chalao.
- **Placeholder images:** placehold.co se aa rahe hain; real photos Cloudinary me Phase 6 me.
