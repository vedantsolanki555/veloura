# Veloura — Project Map

Is file me project ka pura naksha hai: kaunsi pages hain, kaunsi database tables hain.
Har naya step aane par is file ko update karte raho.

**Status updated:** Step 6 Part 3 (polish + performance) ke baad.

---

## A) PAGE LIST

| Page | URL | Kaam | Step | Status |
| --- | --- | --- | --- | --- |
| Home | `/` | Hero banner, featured, categories, new arrivals, Why Veloura | 2 | **Done** |
| Shop | `/shop` | Product grid, category/size/colour/price filters, sort, search, pagination (12/page) | 2+4 | **Done** (Feature 2 polish) |
| Category Shop | `/shop/<slug>` | Ek category ke products (men, women, kids, accessories) | 2 | **Done** |
| Product Detail | `/product/<id>` | Gallery (thumbs + zoom), size + colour selector, per-variant stock, real Add to Cart, WhatsApp order, related products | 3 | **Done** (Add to Cart ab real cart me variant + quantity daalta hai) |
| 404 | (koi bhi galat URL) | "Page not found" + Back to Shop button | 3 | **Done** |
| Register | `/register` | Name, email, phone, password + confirm (CSRF, min 8 chars) | 4 | **Done** |
| Login | `/login` | Email + password (generic error, rate limit 5/15 min per IP+email) | 4 | **Done** |
| Logout | `/logout` | POST-only, CSRF protected | 4 | **Done** |
| My Account | `/account` | Profile + "My orders" (order number, date, items, total, status, thank-you link) | 4 | **Done** |
| Cart | `/cart` | Session cart, quantity update, remove, subtotal/shipping/total, stock-problem blocks checkout | 4 | **Done** (Feature 3) |
| Checkout | `/checkout` | COD address form, server validation (phone 10-digit, pincode 6-digit), CSRF + honeypot, double-submit token | 4 | **Done** (Feature 3) |
| Order Success | `/order/<order_number>/thanks` | COD confirmation, items, WhatsApp button, sirf wahi session khole jo order place ki | 4 | **Done** (Feature 3) |
| Admin Dashboard | `/admin` | Stats: products, categories, orders by status, sales, low stock, recent orders | 5 | **Done** (Feature 1) |
| Admin Products | `/admin/products` | List (search/filter, 20/page), add/edit form + variants editor + Cloudinary/local images, soft/hard delete | 5 | **Done** (Feature 2) |
| Admin Categories | `/admin/categories` | List + add/edit/delete (delete blocked jab tak products hain), auto unique slug | 5 | **Done** (Feature 2) |
| Admin Orders | `/admin/orders` | List (search/filter/pagination), detail, status changes (cancel = stock once), private admin note, WhatsApp button, printable slip, CSV export | 5 | **Done** (Feature 3) |
| Admin Messages | `/admin/messages` | Contact-form messages (newest first, 20/page), unread badge, mark read/unread, delete | 6 | **Done** (Part 1) |
| About | `/about` | Veloura story, values — placeholders `[CITY, STATE]` | 6 | **Done** (Part 1) |
| Contact | `/contact` | Store details [placeholders], WhatsApp button (`WHATSAPP_NUMBER`), message form (CSRF + honeypot + validation) → `contact_messages` table | 6 | **Done** (Part 1) |
| Shipping & Returns | `/shipping-returns` | Shipping/returns policy — live shipping fee + free threshold from config, placeholders for timelines/return window | 6 | **Done** (Part 1) |
| Privacy | `/privacy` | Privacy policy — placeholders for date, support email | 6 | **Done** (Part 1) |
| Terms | `/terms` | Terms of service — placeholders for date, legal name | 6 | **Done** (Part 1) |
| 500 | (koi bhi server error) | "Something went wrong" + Back to Shop | 6 | **Done** (Part 1) |
| SEO + Deploy | — | sitemap, robots, meta, Render deploy | 6 | Parts 1–3 done, Parts 4–5 baaki |

**Feature 1 (Login) done.** **Feature 2 (Cloth list) done** — size + colour filter chips, pagination 12/page (filters URL me rehte hain), hover second image, out-of-stock badge, no N+1 (selectinload). Cart session-based hai (Feature 3 me asli cart).
**Step 5 Feature 1 (Admin access + dashboard) done** — `is_admin` flag, `flask make-admin <email>` CLI, /admin dashboard (totals, orders by status, today's orders, total sales, low stock ≤3, recent 10 orders), sidebar layout (mobile drawer), navbar me sirf admin ko "Admin" link. Normal customer ko /admin par 403, anonymous ko /login redirect. Email validator me `.local` TLD support fix kiya (admin@veloura.local ab login kar sakta hai).
**Step 5 Feature 2 (Categories + products) done** — categories add/edit/delete (products hon par delete blocked, auto unique slug), products list (search, category + stock filter, 20/page pagination), product form (slug auto, discount < price check), variants editor (add/remove rows, duplicate size+colour blocked, stock ≥ 0), images (Cloudinary ya local `app/static/uploads/` fallback, jpg/png/webp max 5 MB, set main / reorder / delete), soft delete (orders hain) vs hard delete (orders nahi), inactive products shop se gayab. Har admin form CSRF-protected.
**Step 5 Feature 3 (Orders) done** — order list (search order no./name/phone, status filter, newest first, 10/page), detail (customer, address, snapshot items, subtotal/shipping/total, COD, status history with changed_by), status changes (New→Confirmed→Shipped→Delivered; Cancelled/Delivered frozen; backwards blocked), cancel = stock restored exactly once (`stock_restored` guard), private admin note (slip par kabhi nahi), WhatsApp customer button (wa.me + order no. + status), printable slip (`/admin/orders/<id>/slip`, clean print CSS), CSV export with current filters. Order model me naye columns: order_number (VLR-YYYYMMDD-XXXX), email, state, subtotal, shipping, payment_method, admin_note, stock_restored, user_id; OrderItem me snapshots (product_name, size, colour); nayi table `order_status_history`. Migration startup par automatically chalta hai (`_migrate_step5_orders`).
**Step 4 Feature 3 (Cart + Checkout COD) done** — session cart (guest + logged-in, `session["cart"]` = variant_id→qty, quantity stock tak capped, same variant do baar = qty badhti hai), /cart page (image, name, size/colour, unit price, update, remove, subtotal + shipping + total, empty state), navbar live cart-count badge, /checkout (COD only: full name, 10-digit Indian mobile, optional email, address/city/state, 6-digit pincode, notes; order summary; logged-in users par account se prefill), server-side validation + CSRF + honeypot + one-time checkout_token (double-submit se duplicate order nahi banta), order creation EK transaction me: variants `FOR UPDATE` lock, stock re-check, stock reduce, Order + snapshot OrderItems + "New" status-history row, rollback agar stock short. Shipping: `SHIPPING_FEE` (default 99) below `FREE_SHIPPING_ABOVE` (default 1999), dono .env me settable. /order/<order_number>/thanks sirf usi session se khulta hai jisne order kiya (403 otherwise), wa.me WhatsApp button `WHATSAPP_NUMBER` se. `flask list-orders` CLI (number, name, phone, total, status, items) + /account par "My orders". Naye orders automatically /admin/orders me dikhte hain aur wahan ke status changes + cancel-restores-stock ke saath kaam karte hain. Code: `app/cart.py` (session helpers), `app/routes/cart.py` (blueprint). Tests: `python tools/test_feature3.py` (52 checks).
**Step 6 Part 1 (Missing pages) done** — /about, /contact, /shipping-returns, /privacy, /terms (real copywriting, [SQUARE BRACKETS] placeholders README me listed). Contact form: CSRF + honeypot + validation (name/email/message), messages `contact_messages` table me save, admin sidebar me "Messages" (unread badge) → /admin/messages (list 20/page, mark read/unread, delete, mailto/tel links). Footer me saare dead `href="#"` hata diye (Contact, Shipping & Returns, About Us, Privacy, Terms). Custom 404 + 500 pages. Shipping page live `SHIPPING_FEE`/`FREE_SHIPPING_ABOVE` config dikhata hai. Tests: `python tools/test_step6.py` (35 checks).
**Step 6 Part 2 (SEO) done** — base.html head me: canonical URL (hamesha clean path, filters/page query kabhi nahi), Open Graph (og:title/description/image/url/type/site_name) + Twitter card (summary_large_image), robots block (public = index,follow; cart/checkout/account/order/login/register/404/403/500 = noindex; admin already noindex,nofollow). Home par Organization JSON-LD (name, slogan "Wear the Elegance.", logo), product page par Product JSON-LD (name, image, price INR, InStock/OutOfStock, brand, url). Favicon: `app/static/img/favicon.svg` + `favicon-32x32.png` + `apple-touch-icon.png` (V monogram, ink + gold, PIL se generate). `/sitemap.xml` (home, /shop, saari categories, sirf active products, static pages; lastmod products par; SITE_URL env var se absolute URLs, mimetype application/xml) aur `/robots.txt` (/admin, /cart, /checkout, /account, /order blocked + Sitemap line). `/product/<slug>` 301 redirect → `/product/<id>` (clean slug share URL, single canonical). Category pages ka <title> ab asli category naam use karta hai (e.g. "Men — Veloura"). Product page ka og:image = uski main product photo (absolute URL). Tests: `python tools/test_step6.py` (65 checks).
**Step 6 Part 3 (Polish + performance) done** — sab product images par `loading="lazy"` + `width`/`height` attributes (cards 800×1000, home 1400×900 — no layout shift), alt text sab images par. Cloudinary uploads ab `quality="auto"` + `fetch_format="auto"` (CDN WebP/AVIF + smart quality). Static files ke cache headers: images/svg/fonts = 1 year ("far future"), css/js = 7 days (`after_request` in app/__init__.py). gzip compression: Flask-Compress==1.14 (requirements.txt me add, har text response compress). Accessibility: global `:focus-visible` gold outline, `--accent-ink` (#8a6540) darker gold for text usages (hero eyebrow, section link, pd-category, static eyebrow — WCAG AA 5:1), burger menu + admin drawer Escape key se band (focus wapas button par), sab forms ke labels already the. Mobile: 992/768/480/400px breakpoints — 360px par bhi koi overflow nahi (container padding 16px, hero font chhota). Loading states: Add-to-Cart button "Adding…", contact form "Sending…", checkout double-submit guard (pehle se). Link crawler: `python tools/crawl_links.py` — saare internal links crawl karta hai, non-200 aur dead `href="#"` report karta hai (test client se, server chalne ki zaroorat nahi). Tests: `python tools/test_step6.py` (84 checks).

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

Abhi rows: **2** (1 admin — `admin@veloura.local`, 1 customer registration)
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
| is_active | Boolean | `False` = shop se gayab (soft delete/hide) — Step 5 F2 me add hua |
| created_at | DateTime | Kab add hua |
| category_id | Integer (FK) | Kis category ka product |

Abhi rows: **18**

### 4. product_images — photos + alt text

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| image_url | String(500) | Local file path ya Cloudinary URL |
| public_id | String(300), nullable | Cloudinary public_id (delete ke liye); NULL = local file — Step 5 F2 me add hua |
| alt | String(300) | Screen readers ke liye alt text |
| position | Integer | Gallery order (0 = pehli / main photo) |
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

### 6. cart — session cart (database table unused)

Cart session me rehta hai (`session["cart"]`, variant_id → quantity) — guests
bina account ke cart use kar sakte hain. DB table `cart` banayi hui hai par
istemaal nahi hoti (session-based cart ne DB rows ki zaroorat khatam kar di).

### 7. orders / 8. order_items / 9. order_status_history — COD orders

orders me ab: id, **order_number** (VLR-YYYYMMDD-XXXX, unique), customer_name,
phone, email, address, city, state, pincode, notes (customer), **admin_note**
(private), status (New/Confirmed/Shipped/Delivered/Cancelled), subtotal,
shipping, payment_method (COD), **stock_restored** (cancel = stock ek hi baar),
total, created_at, user_id (nullable).
order_items me ab snapshots bhi: **product_name, size, colour** (order ke time
ka asli naam/size/colour — product badalne par order nahi badalta).
order_status_history: har status change ki timeline (status, changed_by=admin
email, created_at).

Abhi rows: **0** (test orders cleanup ke baad; checkout ready hai — `python tools/test_feature3.py` se ya browser se order place karke check karo)

### 10. contact_messages — /contact form ke messages (Step 6 Part 1)

| Column | Type | Kaam |
| --- | --- | --- |
| id | Integer (PK) | Unique number |
| name | String(120) | Bhejne wale ka naam |
| email | String(120) | Reply ke liye (lowercase store) |
| phone | String(20), nullable | Optional phone (digits only) |
| message | Text | Customer ka sawaal |
| is_read | Boolean | Admin ne padh liya ya nahi (sidebar badge isi se) |
| created_at | DateTime | Kab aaya |

Admin: `/admin/messages` — list, mark read/unread, delete. Yeh table
`db.create_all()` se app ke pehli baar chalne par automatically ban jaati hai.

---

## Quick notes

- **Local dev server:** `python wsgi.py` → http://127.0.0.1:5000/
- **Feature 1 tests:** `python tools/test_feature1.py` (33 checks — register, login, logout, CSRF, rate limit, next-redirect).
- **Feature 2 tests:** `python tools/test_feature2.py` (53 checks — filters, sort, search, pagination, badges, N+1 query guard).
- **Step 5 Feature 1 tests:** `python tools/test_admin1.py` (29 checks — make-admin CLI, access control, dashboard numbers, sidebar).
- **Step 5 Feature 2 tests:** `python tools/test_admin2.py` (44 checks — category CRUD rules, product form validation, variants, images, delete rules, filters, pagination).
- **Step 5 Feature 3 tests:** `python tools/test_admin3.py` (65 checks — search/filters, status flow, cancel-restock-once, admin note privacy, WhatsApp link, printable slip, CSV export).
- **Step 4 Feature 3 tests:** `python tools/test_feature3.py` (52 checks — cart add/update/remove/cap, checkout validation, CSRF, honeypot, double-submit, guest + logged-in orders, stock reduce/rollback, thank-you session lock, list-orders CLI, My orders, admin status change + cancel-restock).
- **Step 6 tests:** `python tools/test_step6.py` (Part 1: pages + contact + admin messages; Part 2: SEO — canonical, OG/Twitter, JSON-LD, sitemap, robots, noindex, favicons, slug redirect; Part 3: lazy images, cache headers, gzip, a11y, crawl; 84 checks).
- **Link crawler:** `python tools/crawl_links.py` — crawls every internal link via the test client; exits 1 if any non-200 or dead `href="#"` is found.
- **Photo uploads:** `CLOUDINARY_URL` set hai to Cloudinary; nahi hai to `app/static/uploads/` (git-ignored, README me clearly documented).
- **Photos:** sab images local hain (`app/static/img/`), koi external hotlink nahi.
  Credits: `app/static/img/products/CREDITS.md` — dobara download: `python tools/fetch_images.py`
- **Admin login (abhi):** `admin@veloura.local` / `admin123` — production se pehle change karna zaroori hai.
- **WhatsApp:** `.env` me `WHATSAPP_NUMBER` (digits + country code, no `+`) — product page ka "Order on WhatsApp" button isi se banta hai.
- **Seed data wapas chahiye?** `instance/veloura.db` delete karo, phir `python seed.py` chalao.
