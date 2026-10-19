# Veloura Step 5: Admin Panel (ONE FEATURE AT A TIME)

I am the only owner. Admin is for me only. Keep the Veloura design system (ink, ivory, champagne gold, Cormorant Garamond + Jost, thin gold borders, 0.3s transitions) but keep the admin UI clean, simple and mobile friendly. Beginner-friendly comments. Read docs/PROJECT_MAP.md first and keep it updated.

## GLOBAL RULES
- Build in this order: Feature 1 (Admin access + Dashboard), Feature 2 (Categories + Products), Feature 3 (Orders).
- Check the real code and git log first and skip anything already DONE. Do not guess.
- After each feature: test it, fix every failure, re-test, update docs/PROJECT_MAP.md, follow the GIT STEPS below (one commit and push per feature), then continue to the next feature.
- Stop early ONLY if a push fails, a secret or database file is about to be committed, or a test still fails after 3 fix attempts. Then show me the exact error.
- Check server console and browser console for errors on every feature.

## GIT STEPS (after each feature passes its tests)
1. `git status` and review what will be committed.
2. Never commit .env, server.log, *.log, venv/, *.db, instance/ or any secret. Add any missing entries to .gitignore first.
3. `git add -A`, then commit with a clear message: "feat: admin access and dashboard" / "feat: admin categories and products" / "feat: admin orders".
4. `git push origin main`
5. Show `git log --oneline -3` and confirm the push worked.
Never force-push. Never rewrite history. If a push fails, STOP and show me the error.

## FEATURE 1: ADMIN ACCESS + DASHBOARD
1. Add an is_admin boolean to the User model (default False). Update the database safely (migration or clear instructions; do not break existing data).
2. CLI command `flask make-admin <email>` that turns an existing registered user into an admin. No hardcoded admin username or password anywhere.
3. All /admin routes live in one Blueprint protected by one decorator: must be logged in AND is_admin, otherwise redirect to /login (not logged in) or show 403 (logged in but not admin). No admin link shown in the public navbar for non-admins; admins see a small "Admin" link.
4. /admin dashboard: total products, total categories, total orders, orders by status (New, Confirmed, Shipped, Delivered, Cancelled), today's orders, total sales of non-cancelled orders, low-stock variants (stock <= 3), and the 10 most recent orders.
5. Admin layout: simple sidebar (Dashboard, Products, Categories, Orders, View store, Logout) that collapses on mobile.
6. Test: anonymous user, normal customer, admin user, make-admin command, dashboard numbers match the database.

## FEATURE 2: CATEGORIES + PRODUCTS
1. Categories: list, add, edit, delete. Do not allow deleting a category that still has products (show a friendly message). Auto-generate a unique slug.
2. Products list: search, filter by category and stock status, pagination (20 per page). Show thumbnail, name, category, price, discount price, total stock, featured / new / active flags.
3. Add and edit product form: name, slug (auto, editable), category, description, fabric and care, price, discount price (must be lower than price), featured, new arrival, active (inactive products hidden from the store).
4. Variants editor on the same form: add and remove rows of size, colour, stock (stock >= 0). Prevent duplicate size+colour combinations.
5. Images: upload multiple images per product to Cloudinary (CLOUDINARY_URL from env). Check file type (jpg, png, webp only) and size (max 5 MB each). Set a main image, reorder images, delete an image. Store the Cloudinary URL and public_id. If Cloudinary is not configured, fall back to saving in app/static/uploads/ and tell me clearly in the README. Never commit uploaded files.
6. Delete product: soft delete (set inactive) if it has orders, hard delete only if it has no orders. Ask for confirmation.
7. CSRF on every form (Flask-WTF), server-side validation with clear error messages, flash messages for success.
8. Test: create category, create product with 3 images and 3 variants, edit it, make it inactive and confirm it disappears from /shop, delete rules, invalid upload, duplicate variant, discount price higher than price.

## FEATURE 3: ORDERS
1. Orders list: search by order number, customer name or phone; filter by status; sort newest first; pagination. Show order number, date, customer, phone, total, status.
2. Order detail: customer details, address, notes, items (snapshot name, size, colour, price, quantity), subtotal, shipping, total, payment method (COD), status history.
3. Change status: New, Confirmed, Shipped, Delivered, Cancelled. When an order is Cancelled, put the item quantities back into stock (only once, never twice). Do not allow changing a Cancelled or Delivered order back to an earlier status.
4. Add an internal admin note on each order (private, never shown to the customer).
5. Buttons: "WhatsApp customer" (wa.me link to the customer's phone with a prefilled message including the order number and status) and a printable order slip page (clean print CSS).
6. Export: "Download orders CSV" with the current filters applied.
7. Test: status changes, cancel returns stock exactly once, blocked status moves, search and filters, CSV content, printable slip.

## FINAL REPORT
One checklist of every item in all 3 features as DONE or MISSING with one line of proof each, plus `git log --oneline -5`.
