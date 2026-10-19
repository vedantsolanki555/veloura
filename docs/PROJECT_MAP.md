# Veloura — Project Map

Is file me project ka pura naksha hai: kaunsi pages hain, kaunsi database tables hain.
Har naya step aane par is file ko update karte raho.

**Status updated:** Step 5 Feature 1 (Admin access + Dashboard) ke baad.

---

## A) PAGE LIST

| Page | URL | Kaam | Step | Status |
| --- | --- | --- | --- | --- |
| Home | `/` | Hero banner, featured, categories, new arrivals, Why Veloura | 2 | **Done** |
| Shop | `/shop` | Product grid, category/size/colour/price filters, sort, search, pagination (12/page) | 2+4 | **Done** (Feature 2 polish) |
| Category Shop | `/shop/<slug>` | Ek category ke products (men, women, kids, accessories) | 2 | **Done** |
| Product Detail | `/product/<id>` | Gallery (thumbs + zoom), size + colour selector, per-variant stock, WhatsApp order, related products | 3 | **Done** (Add to Cart abhi "Cart is coming soon" dikhata hai — real cart Step 4 me) |
| 404 | (koi bhi galat URL) | "Page not found" + Back to Shop button | 3 | **Done** |
| Register | `/register` | Name, email, phone, password + confirm (CSRF, min 8 chars) | 4 | **Done** |
| Login | `/login` | Email + password (generic error, rate limit 5/15 min per IP+email) | 4 | **Done** |
| Logout | `/logout` | POST-only, CSRF protected | 4 | **Done** |
| My Account | `/account` | Profile + "My orders" placeholder (real orders Feature 3 me) | 4 | **Done** |
| Cart | `/cart` | Session cart, quantity update, shipping + total | 4 | Baaki |
| Checkout | `/checkout` | Address form (COD only), CSRF + honeypot | 4 | Baaki |
| Order Success | `/order/<id>` | COD order confirmation | 4 | Baaki |
| Admin Dashboard | `/admin` | Stats: products, categories, orders by status, sales, low stock, recent orders | 5 | **Done** (Feature 1) |
| Admin Products | `/admin/products` | Products add/edit/delete | 5 | Baaki |
| Admin Categories | `/admin/categories` | Categories add/edit/delete | 5 | Baaki |
| Admin Orders | `/admin/orders` | Orders dekhna + status update karna | 5 | Baaki |
| SEO + Deploy | — | sitemap, robots, meta, Render deploy | 6 | Baaki |

**Feature 1 (Login) done.** **Feature 2 (Cloth list) done** — size + colour filter chips, pagination 12/page (filters URL me rehte hain), hover second image, out-of-stock badge, no N+1 (selectinload). Cart session-based hai (Feature 3 me asli cart).
**Step 5 Feature 1 (Admin access + dashboard) done** — `is_admin` flag, `flask make-admin <email>` CLI, /admin dashboard (totals, orders by status, today's orders, total sales, low stock ≤3, recent 10 orders), sidebar layout (mobile drawer), navbar me sirf admin ko "Admin" link. Normal customer ko /admin par 403, anonymous ko /login redirect. Email validator me `.local` TLD support fix kiya (admin@veloura.local ab login kar sakta hai).

---

## B) STEP 3 STATUS (items 1–14)

| # | Item | Status |
| --- | --- | --- |
| 1 | Gallery — main image + clickable thumbnails + hover zoom + mobile scroll | **Done** |
| 2 | Colour swatches (hex map + text-chip fallback) | **Done** |
| 3 | Size + colour = one variant; stock, disabled combos, qty max = variant stock | **Done** |
| 4 | "Order on WhatsApp" — `WHATSAPP_NUMBER` env se, wa.me prefilled message | **Done** |
| 5 | Add to Cart button + "Cart is coming soon" (English) | **Done** |
| 6 | Price format `₹2,499` — `inr` Jinja filter (`app/__init__.py`) | **Done** |
| 7 | Sort by effective price (discount chaho to wahi) | **Done** |
| 8 | Navbar search keeps category + price filters | **Done** |
| 9 | Per-page meta descriptions (Home, Shop, Category, Product) | **Done** |
| 10 | Navbar se "Login" link hata di | **Done** |
| 11 | Seed test data: 1 variant stock 0 + 1 product out of stock | **Done** |
| 12 | Yeh file (PROJECT_MAP) reality ke hisaab se | **Done** |
| 13 | Local product photos (Pexels) + `CREDITS.md`, sab 300 KB se kam | **Done** |
| 14 | Test loop — app chala kar sab check kiya, errors fix kiye | **Done** |

---

## C) DATABASE TABLES

Database file (local dev): `instance/veloura.db`

### 1. users — customer + admin accounts

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| name | String(120) | Customer ka poora naam (admin rows me NULL ho sakta hai) |
| email | String(120), unique | Login email — hamesha lowercase store hota hai |
| phone | String(20) | Customer ka phone (admin rows me NULL ho sakta hai) |
| password_hash | String(256) | Password ka hash (plain text kabhi nahi) |
| is_admin | Boolean | `True` = admin |
| created_at | DateTime | Account kab bana |

Abhi rows: **1** (sirf admin — `admin@veloura.local`; test users cleanup me delete ho jaate hain)
Purani database me ye columns `_migrate_user_columns()` se startup par add ho jaate hain (app/__init__.py).

### 2. categories — product groups

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| name | String(80), unique | Jaise "Men" |
| slug | String(80), unique | URL ke liye, jaise "men" |

Abhi rows: **4**

### 3. products — kapdon ki list

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| name / slug / description | — | Naam, URL naam, details |
| price | Numeric(10,2) | Original price (₹) |
| discount_price | Numeric(10,2), nullable | Sale price; NULL = no discount |
| fabric_care | Text | Fabric aur care instructions |
| is_featured / is_new | Boolean | Home page sections |
| created_at | DateTime | Kab add hua |
| category_id | Integer (FK) | Kis category ka product |

Abhi rows: **18**

### 4. product_images — photos + alt text

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| image_url | String(500) | Local file path, jaise `/static/img/products/mens-silk-kurta-1.jpg` |
| alt | String(300) | Screen readers ke liye alt text |
| position | Integer | Gallery order (0 = pehli photo) |
| product_id | Integer (FK) | Kis product ki photo |

Abhi rows: **52** (har product ki 2–3 photos, sab local, `app/static/img/products/` me)

### 5. product_variants — size / colour / stock

| Column | Type | Kaam |
| --- | --- | --- |
| size | String(20) | S, M, L, XL, Free, 2-3Y etc. |
| colour | String(50) | Indigo, Black etc. |
| stock | Integer | Kitne piece available |
| product_id | Integer (FK) | Kis product ka variant |

Abhi rows: **62** — test ke liye: `mens-cotton-chinos` size **M** = 0 stock, poori `kids-graphic-tee` = **0 stock**

### 6. cart — Step 4 ka session cart

Abhi rows: **0** (Step 4 me bharegi)

### 7. orders / 8. order_items — COD orders (Step 4)

Abhi rows: **0**

---

## Quick notes

- **Local dev server:** `python wsgi.py` → http://127.0.0.1:5000/
- **Feature 1 tests:** `python tools/test_feature1.py` (33 checks — register, login, logout, CSRF, rate limit, next-redirect).
- **Feature 2 tests:** `python tools/test_feature2.py` (53 checks — filters, sort, search, pagination, badges, N+1 query guard).
- **Step 5 Feature 1 tests:** `python tools/test_admin1.py` (29 checks — make-admin CLI, access control, dashboard numbers, sidebar).
- **Photos:** sab images local hain (`app/static/img/`), koi external hotlink nahi.
  Credits: `app/static/img/products/CREDITS.md` — dobara download: `python tools/fetch_images.py`
- **Admin login (abhi):** `admin@veloura.local` / `admin123` — production se pehle change karna zaroori hai.
- **WhatsApp:** `.env` me `WHATSAPP_NUMBER` (digits + country code, no `+`) — product page ka "Order on WhatsApp" button isi se banta hai.
- **Seed data wapas chahiye?** `instance/veloura.db` delete karo, phir `python seed.py` chalao.
