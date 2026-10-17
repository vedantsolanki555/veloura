# Veloura Step 4: Login, Cloth List, Cart (ONE FEATURE AT A TIME)

Keep the Veloura design system (ink, ivory, champagne gold, Cormorant Garamond + Jost, thin gold borders, 0.3s transitions). Mobile-first. Beginner-friendly comments. Read docs/PROJECT_MAP.md first and keep it updated.

## GLOBAL RULES
- Build ONLY ONE feature at a time, in this order: Feature 1 (Login), Feature 2 (Cloth list), Feature 3 (Cart + Checkout).
- After each feature: test it, fix every failure, re-test, update docs/PROJECT_MAP.md, then do the GIT STEPS below, report the checklist as DONE or MISSING with one line of proof each, and STOP. Do NOT start the next feature until I say "go".
- Do NOT build the admin panel (that is Step 5).
- Check server console and browser console for errors on every feature.

## GIT STEPS (after each feature passes its tests)
Before Feature 1, run `git status` and `git remote -v`. If there is no remote called origin, STOP and tell me. Do not create repos, do not ask for tokens or passwords, do not try workarounds.
Make sure .gitignore covers: .env, venv/, __pycache__/, *.db, instance/, .DS_Store. Run `git ls-files` and confirm no .env, no database file and no secrets are tracked. If any are tracked, run `git rm --cached` on them, tell me, and remind me to rotate any secret that was ever committed.
Then for each feature:
1. `git status` and review what will be committed.
2. `git add -A`
3. Commit with a clear message: "feat: customer login" / "feat: cloth list polish" / "feat: cart, checkout and COD orders".
4. `git push origin main`
5. Show `git log --oneline -3` and confirm the push worked.
Never force-push. Never rewrite history. Never commit secrets or database files. If a push fails, STOP and show me the error.

## FEATURE 1: CUSTOMER LOGIN (guest checkout stays allowed)
1. User model: id, name, email (unique, lowercase), phone, password_hash, created_at. Update the database safely (migration or clear instructions; do not break existing data).
2. Pages: /register (name, email, phone, password + confirm), /login, /logout, /account (profile + "My orders" list placeholder until Feature 3).
3. Use Flask-Login. Hash passwords with werkzeug. Minimum password length 8.
4. Security: CSRF on every form (Flask-WTF), generic error "Invalid email or password" (never reveal which one is wrong), simple login rate limit (e.g. 5 failed tries per 15 minutes per IP+email), secure session cookies (HttpOnly, SameSite=Lax, Secure in production), validate the "next" redirect so it only goes to our own site.
5. Navbar: logged out shows Login / Register; logged in shows the user's first name and Logout. Premium styling, works on mobile menu.
6. Test: register, duplicate email, wrong password, correct login, logout, protected /account redirect to login, bad "next" URL ignored, rate limit.

## FEATURE 2: CLOTH LIST (Shop page audit and polish, do not rebuild)
1. Audit the existing Home and /shop pages. Fix what is missing or broken:
   - Product grid with image, name, effective price (sale price + struck-through MRP), second image on hover, out-of-stock badge, New/Sale tags.
   - Filters: category, size, colour, price range. Sort: newest, price low-high, high-low (by effective price). Search. All filters kept in the URL and preserved across search/sort/pagination.
   - Pagination (12 per page), empty-results state, result count.
   - Responsive 2-column mobile grid, lazy-loaded images, no N+1 database queries.
   - Category pages and Home "New arrivals" and "Featured" sections work and link correctly.
2. Test every filter and sort combination, empty results, pagination, mobile layout, and page load without errors.

## FEATURE 3: CART, CHECKOUT (COD only) AND ORDERS
A. Cart (session-based; guests and logged-in users)
1. Real Add to Cart replacing "Cart is coming soon". Store variant_id + quantity in the Flask session. Quantity never exceeds that variant's stock. Adding the same variant twice increases quantity.
2. /cart page: image, name, size, colour, unit price, quantity update, remove, subtotal, shipping, total. Shipping is free above FREE_SHIPPING_ABOVE, else SHIPPING_FEE (env vars, defaults 1999 and 99, add to .env.example). Friendly empty-cart state with "Continue shopping".
3. Navbar cart link shows a live item-count badge and works (no href="#").
4. If a cart item's variant goes out of stock or stock drops, show a clear message and block checkout until fixed.
B. Checkout (Cash on Delivery only)
5. /checkout: full name, phone (10-digit Indian mobile), email (optional), address, city, state, pincode (6 digits), notes, with order summary beside the form. Redirect to cart if empty. Prefill from the account if logged in.
6. Server-side validation with clear errors, CSRF protection, hidden honeypot field against bots.
7. On submit, in ONE database transaction: re-check stock for every item, create Order + OrderItems, reduce stock, clear the cart. If stock is not enough, roll back and show a friendly message. Prevent double-submit.
8. Order fields: unique non-guessable order_number (e.g. VLR-20261016-4821), status default "New", payment_method "COD", subtotal, shipping, total, customer details, created_at, user_id (nullable, set when logged in). OrderItem stores a snapshot (product name, size, colour, unit price, quantity). Update the database safely.
C. Thank-you page
9. /order/<order_number>/thanks: order number, items, total, "Pay cash on delivery" note, and a "Send order details on WhatsApp" button (wa.me link using WHATSAPP_NUMBER with a prefilled summary). Only the session that placed the order can open it.
D. Owner and customer views
10. CLI command `flask list-orders` (number, name, phone, total, status, items). Fill the "My orders" list on /account for logged-in users.
E. Test
Add to cart, same variant twice, quantity above stock, update, remove, empty-cart checkout, invalid phone/pincode, valid order (guest and logged-in), stock reduced after order, out-of-stock during checkout, double-submit, thank-you page from another session, `flask list-orders`, My orders.
