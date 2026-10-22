# Veloura

Premium clothing store website. Built with Python Flask, SQLAlchemy, PostgreSQL, and Jinja2 templates.

## Project status

- **Step 1 (done):** project setup, database models, seed data, simple home page.
- **Steps 2–5 (done):** design, cloth list, product detail, customer login, admin panel, cart, checkout, COD orders.
- **Step 6 (in progress):** SEO, polish, production readiness, Render deployment. Part 1 (missing pages) done.

## Placeholders you must fill in

These appear in `[SQUARE BRACKETS]` on the live pages. Search the templates
for `[` and replace them with your real details before launch:

| Placeholder | Where it shows |
| --- | --- |
| `[STUDIO ADDRESS — full street address, city, state, pincode]` | `/contact` |
| `[PHONE NUMBER — e.g. +91 98765 43210]` | `/contact` |
| `[SUPPORT EMAIL — e.g. hello@veloura.in]` | `/contact`, `/privacy` |
| `[CITY, STATE]` | `/about` |
| `[DATE — e.g. 22 October 2026]` | `/privacy`, `/terms` (Last updated) |
| `[X–Y business days]` | `/shipping-returns` |
| `[N days]` (return window, exchange window) | `/shipping-returns` |
| `[free / paid by customer]` (return shipping) | `/shipping-returns` |
| `[original payment method / bank account]`, `[X days]` (refund) | `/shipping-returns` |
| `[48 hours]` (damaged-item window) | `/shipping-returns` |
| `[X days]` (data requests) | `/privacy` |
| `[18 years or older]` | `/terms` |
| `[BUSINESS LEGAL NAME]` | `/terms` |

## Requirements

- Python 3.12+

## How to run (local development)

```bash
# 1. Create and activate a virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file from the example
copy .env.example .env
# Then open .env and set SECRET_KEY to a long random string.

# 4. Create tables + seed data (safe to re-run; skips if data already exists)
python seed.py

# 5. Start the development server
python wsgi.py
```

Open <http://127.0.0.1:5000/> in your browser. You should see "Veloura".

## Configuration (environment variables)

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session signing key. Required. |
| `DATABASE_URL` | PostgreSQL connection string. If unset, app uses SQLite locally (`instance/veloura.db`) — **dev fallback only, do not use SQLite in production**. |
| `CLOUDINARY_URL` | Cloudinary credentials for product image uploads (admin panel). Format: `cloudinary://API_KEY:API_SECRET@CLOUD_NAME` |
| `WHATSAPP_NUMBER` | Digits-only WhatsApp number (country code, no `+`) for the WhatsApp order buttons. |
| `SITE_URL` | Public site URL (e.g. `https://veloura.onrender.com`) — used in `sitemap.xml` and `robots.txt`. Optional locally. |
| `FLASK_ENV` | `development` or `production`. |

Secrets live only in environment variables (via `.env` locally, Render dashboard in production). Never hardcode them.

## Product image uploads (important)

Admin product images are saved in **one of two places**:

1. **Cloudinary (production / recommended).** If `CLOUDINARY_URL` is set in
   `.env`, every uploaded image goes to Cloudinary and the app stores the
   secure URL + `public_id` in the database.
2. **Local fallback (development).** If `CLOUDINARY_URL` is **not** set, images
   are saved to `app/static/uploads/` instead. This keeps the admin panel
   working locally with no Cloudinary account.

Uploaded files in `app/static/uploads/` are **never committed to git**
(`.gitignore` covers the folder) and the folder is safe to delete at any time.
Only JPG, PNG and WEBP images up to 5 MB each are accepted.

## Demo seed data (development only)

`python seed.py` inserts **demo content**: 4 categories, 18 products and one
local admin (`admin@veloura.local`). It is safe to re-run — it skips everything
if data already exists and never deletes anything.

- **It refuses to run when `FLASK_ENV=production`** (use `python seed.py
  --force` only if you really want demo data on the live site).
- Before launch, delete the demo content from the admin panel: **Products →
  each product → Delete** (a product with real orders is only hidden, never
  destroyed), **Categories → Delete**, and finally delete the demo admin user
  under your own account settings. Your real data is never touched by seed.py.
- On a brand-new production database, create tables with `flask init-db`
  (or let the Render start command run `flask db upgrade`), then add your own
  products through the admin panel.

## Database migrations (Flask-Migrate)

The schema is tracked in `migrations/` (baseline migration from Step 6):

```bash
flask db migrate -m "what changed"   # create a migration after changing models
flask db upgrade                     # apply migrations (Render runs this on deploy)
flask init-db                        # fresh empty DB only: create all tables at once
```

Never run `flask db upgrade` against a database that has live data without
reviewing the generated migration first.

# Deploy Veloura (beginner step-by-step)

> **Two people are involved: OpenCode (the code) and you (the accounts).**
>
> **Done for you by OpenCode — nothing to do here:**
> `render.yaml` blueprint, `Procfile`, `gunicorn.conf.py`, `runtime.txt`
> (Python 3.12.10), Flask-Migrate baseline migration (`flask db upgrade` runs
> automatically on every deploy), `/healthz` health check, HTTPS redirect +
> security headers, `postgres://` → `postgresql://` auto-fix (the bug that
> crashed your first deploy), production `SECRET_KEY` guard, and this guide.
>
> **Steps YOU must do yourself** (only you can create accounts and see
> secrets): steps 1–5 below (Neon, Cloudinary, Render, first admin account,
> real products), then the launch checklist in step 8.

## 1. Create the database (Neon) — ~5 minutes, YOU do this

1. Go to <https://neon.tech> and sign up (free plan is enough).
2. Create a project, e.g. `veloura`. Pick a region close to your Render region.
3. Open **Connection Details**, choose the **Pooled** connection string
   (it starts with `postgresql://…`), and copy it.
4. Keep it private — it contains your password. You will paste it into the
   Render dashboard in step 3. **Never** put it in this repository.

## 2. Create the image host (Cloudinary) — ~5 minutes, YOU do this

1. Go to <https://cloudinary.com> and sign up (free plan is enough).
2. From the dashboard, copy your **Cloud name**, **API Key** and
   **API Secret**.
3. Build the value yourself (the secret never touches git):

   ```
   cloudinary://API_KEY:API_SECRET@CLOUD_NAME
   ```

4. You will paste that whole string as `CLOUDINARY_URL` in step 3.

## 3. Create the site (Render) — ~10 minutes, YOU do this

1. Push this repository to GitHub (if you have not already).
2. On <https://dashboard.render.com> click **New → Blueprint**.
3. Connect your (private) GitHub repo `veloura` and let Render read
   `render.yaml`.
4. Choose the **Free** plan when asked.
5. Render now prompts for the environment variables (names come from
   `render.yaml`, values stay only in Render):
   | Variable | What to enter |
   | --- | --- |
   | `SECRET_KEY` | Leave the generated value as-is. |
   | `DATABASE_URL` | The Neon pooled connection string from step 1. |
   | `CLOUDINARY_URL` | The `cloudinary://…` string from step 2. |
   | `WHATSAPP_NUMBER` | Digits only, with country code, no `+` (e.g. `919876543210`). |
   | `SHIPPING_FEE` | e.g. `99` (optional). |
   | `FREE_SHIPPING_ABOVE` | e.g. `1999` (optional). |
   | `SITE_URL` | Filled automatically from your `…onrender.com` URL. |
   | `FLASK_ENV` | Already `production` — don't change it. |
6. Click **Deploy**. The build runs `pip install -r requirements.txt`,
   then the start command runs `flask db upgrade` (creates every table on
   the empty Neon database) and boots `gunicorn wsgi:app`.
7. Watch the **Logs** tab: it should end with `Veloura started in production
   mode.` and no tracebacks. Open your `https://veloura.onrender.com` URL —
   if it slept, the first visit takes ~1 minute.

> Tables are handled for you: Render runs `flask db upgrade` on **every**
> deploy (fresh DB → baseline schema, later deploys → migrations only).
> If you ever start from a completely empty database outside Render, run
> `flask init-db` instead (creates tables, never deletes data).

## 4. Create YOUR admin account — ~5 minutes, YOU do this

`seed.py` is demo-only and refuses to run in production, so your real admin
comes from your own registration:

1. On the live site, open `/register` and create **your** account
   (use your real email — this is your customer account too).
2. Promote it to admin. Render's free plan has **no web shell**, so run it
   from your own machine against the production database:

   ```bash
   # PowerShell (Windows) — paste YOUR Neon string, never commit it
   $env:DATABASE_URL = "postgresql://…your neon url…"
   flask make-admin you@example.com
   ```

   (On the paid Render plan you could instead use the dashboard **Shell**
   tab and run the same `flask make-admin you@example.com` there.)
3. Log out, then log in at `/login` with that account and open `/admin`.

## 5. Real content instead of demo data — YOU do this

1. In `/admin`: **Categories** → add your real categories; **Products** →
   add your real products with your own photos (they upload straight to
   Cloudinary — the admin warning banner disappears once `CLOUDINARY_URL`
   is set).
2. Delete the demo products/categories (see
   [Demo seed data](#demo-seed-data-development-only)) — a product that
   already has orders is only hidden, never destroyed.

## 6. Test the store — YOU do this

1. Place a small **Cash on Delivery** order from the live site.
2. Confirm it appears in `/admin → Orders` with the correct status
   (`New`), and that the status flow (Confirm → Ship → Deliver) works.
3. On the product page, click a **WhatsApp order button** — it must open a
   chat pre-filled with the product details and your number.

## 7. Free plan notes (read once)

- The site **sleeps after 15 minutes** with no visitors; the next visit
  takes ~60 seconds to wake it up. After that it is normal again.
- Free instances get **750 instance-hours/month**; a sleeping service uses
  none. Moving up removes sleeping — Render **Settings → Instance** and
  pick a paid plan whenever you are ready.
- The disk is **wiped on every redeploy/restart** — that is why uploads
  go to Cloudinary and the database lives on Neon. Nothing local ever
  matters in production.
- **Custom domain + HTTPS:** Render **Settings → Domains** → add your
  domain, follow the DNS instructions; Render provisions the HTTPS
  certificate automatically. Then update `SITE_URL` to your domain.

## 8. Launch checklist

- [ ] Every `[PLACEHOLDER]` in the pages is filled (list at the top of
      this README: address, phone, support email, return window…).
- [ ] Demo products and categories deleted; real photos uploaded.
- [ ] Shipping policy, returns window and privacy text read as your real
      policy.
- [ ] One test COD order placed, confirmed in `/admin → Orders`, status
      updated, WhatsApp link checked.
- [ ] `SITE_URL` set to your final domain (used by sitemap/robots).
- [ ] Google Search Console: add the property, submit
      `https://your-domain/sitemap.xml`, press **Indexing → Request
      indexing** for the home page.

## Project structure

```
Veloura/
├── app/
│   ├── __init__.py      # App factory — creates the Flask app
│   ├── models.py        # Database models (tables)
│   ├── routes/          # URL handlers (Blueprints)
│   │   ├── __init__.py
│   │   └── main.py      # Home page route
│   ├── templates/       # Jinja2 HTML templates
│   │   └── home.html
│   └── static/          # CSS, JS, images served to the browser
│       ├── css/style.css
│       └── js/main.js
├── config.py            # App configuration (reads env vars)
├── wsgi.py              # Entry point for gunicorn / python wsgi.py
├── seed.py              # Fills the database with sample data
├── requirements.txt     # Python packages
├── .env.example         # Template for your .env file
└── .gitignore
```
