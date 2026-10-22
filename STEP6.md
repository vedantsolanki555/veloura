# Veloura Step 6: SEO, Polish and Deployment on Render (ONE PART AT A TIME)

I am the only owner and a beginner. Keep the Veloura design system (ink, ivory, champagne gold, Cormorant Garamond + Jost, thin gold borders, 0.3s transitions). Beginner-friendly comments. Read docs/PROJECT_MAP.md first and keep it updated.

## PRECONDITION
Check the real code and git log. Cart, checkout and COD orders (Step 4 Feature 3) must be DONE and working. If not, STOP and tell me. Do not deploy a store that cannot take orders.

## GLOBAL RULES
- Build in this order: Part 1 (Missing pages), Part 2 (SEO), Part 3 (Polish and performance), Part 4 (Production readiness), Part 5 (Deployment files and guide).
- After each part: test it, fix every failure, re-test, update docs/PROJECT_MAP.md, then commit and push (one commit per part, message like "feat: seo", "chore: production readiness"), then continue.
- Never commit .env, server.log, *.log, uploads, *.db or any secret. Never force-push.
- Stop early ONLY if a push fails, a secret is about to be committed, or a test still fails after 3 fix attempts. Then show me the exact error.

## PART 1: MISSING PAGES (footer links must not be dead)
1. /about, /contact, /shipping-returns, /privacy, /terms. Elegant, short, real copywriting for Veloura (tagline "Wear the Elegance."). Use clear placeholders in [SQUARE BRACKETS] for things only I know (address, phone, email, return window) and list every placeholder in the README so I can fill them in.
2. Contact page: store details, WhatsApp button (WHATSAPP_NUMBER env var), and a simple contact form that saves messages to the database (CSRF + honeypot + validation). Show messages in the admin sidebar under "Messages".
3. Fix every remaining href="#" in navbar and footer.
4. Custom 404 and 500 pages in the Veloura style.

## PART 2: SEO
1. Unique title and meta description on every public page. Product pages use product name and short description. Category pages use category name.
2. Open Graph and Twitter card tags (title, description, image). Product pages use the main product image.
3. Canonical URLs. Clean slugs. No duplicate content from filter or sort URLs (canonical points to the base page).
4. /sitemap.xml (home, categories, active products, static pages) and /robots.txt (block /admin, /cart, /checkout, /account, /order). Sitemap uses the SITE_URL env var.
5. JSON-LD structured data: Organization on the home page, Product (name, image, price in INR, availability) on product pages.
6. Favicon and apple-touch icon with a "V" monogram (simple SVG/PNG in the gold and ink colours).
7. Admin, cart, checkout, account and order pages get <meta name="robots" content="noindex">.

## PART 3: POLISH AND PERFORMANCE
1. Images: lazy loading, width and height attributes (no layout shift), alt text on all images, Cloudinary auto format and quality for uploaded images.
2. Keep CSS and JS small. Add far-future cache headers for static files and gzip or brotli compression if easy.
3. Accessibility: visible focus states, button and form labels, colour contrast checked against ink/ivory/gold, keyboard friendly menus and gallery.
4. Mobile check at 360px and 390px widths on Home, Shop, Product, Cart, Checkout, Account, Admin.
5. Loading and empty states, friendly flash messages everywhere.
6. Test every page for console errors and broken links (write a small script that crawls internal links and reports any non-200).

## PART 4: PRODUCTION READINESS
1. config.py: separate development and production config. Production: DEBUG off, SECRET_KEY required from env (app refuses to start without it), SESSION_COOKIE_SECURE, HTTPONLY, SAMESITE=Lax, PREFERRED_URL_SCHEME https, trust the proxy headers on Render (ProxyFix).
2. Database: DATABASE_URL from env. Convert a "postgres://" URL to "postgresql://" automatically. Use a PostgreSQL driver in requirements.txt. Add database migrations (Flask-Migrate) so tables are created and updated safely on the live database. Add a `flask init-db` command (create tables only, does NOT delete data) and keep seed.py as DEMO ONLY: it must refuse to run when FLASK_ENV=production unless I pass --force, and it must never wipe existing real data without a clear warning.
3. Security headers: Content-Security-Policy (allow Google Fonts, Cloudinary and our own images), X-Content-Type-Options, X-Frame-Options, Referrer-Policy. HTTPS redirect in production.
4. Login and checkout rate limiting kept; add rate limiting to the contact form.
5. Logging to stdout (Render shows it), no secrets or personal data in logs. A /healthz route returning 200 for Render's health check.
6. Uploads: production must use Cloudinary only (Render's free disk is wiped on every redeploy). If CLOUDINARY_URL is missing in production, show a clear warning in the admin.
7. Remove demo/placeholder images from production flow: the seed data is demo only and I will delete it from the admin before launch (describe how in the README).
8. Run a dependency check (pip list --outdated and a known-vulnerability check such as pip-audit if available) and fix anything serious.

## PART 5: DEPLOYMENT FILES AND GUIDE
1. Add gunicorn config (Procfile or render.yaml): `gunicorn wsgi:app` with sensible workers and timeout. Add runtime.txt or the Python version setting.
2. render.yaml (blueprint) with the web service, build command (pip install -r requirements.txt), start command (run migrations then gunicorn), health check path /healthz, and the list of env var NAMES (no values): SECRET_KEY, DATABASE_URL, CLOUDINARY_URL, WHATSAPP_NUMBER, SITE_URL, FREE_SHIPPING_ABOVE, SHIPPING_FEE, FLASK_ENV=production.
3. README "Deploy Veloura" guide written for a beginner, step by step, covering things only I can do:
   a. Create a free PostgreSQL database (Neon) and copy the connection string.
   b. Create a Cloudinary account and copy CLOUDINARY_URL.
   c. On Render: New Web Service, connect my private GitHub repo (veloura), choose the free plan, add the env vars above.
   d. After the first deploy: run `flask init-db`, register my account on the live site, run `flask make-admin <email>` in the Render shell, log in to /admin.
   e. Add real categories and products with my own photos, delete demo data.
   f. Place a test COD order, confirm it appears in /admin/orders, and check the WhatsApp links.
   g. Free plan notes: the site sleeps after inactivity and the first visit is slow; how to upgrade later; how to add a custom domain and HTTPS.
   h. Launch checklist (placeholders filled, real photos, policies read, test order, sitemap submitted to Google Search Console).
4. Tell me clearly which steps OpenCode did and which steps I must do myself.

## FINAL REPORT
One checklist of every item in all 5 parts as DONE or MISSING with one line of proof each, plus `git log --oneline -6`, plus the list of env vars I must set on Render.
