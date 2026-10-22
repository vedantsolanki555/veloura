// Veloura front-end JS
// Sections:
//   1) Mobile burger menu
//   2) Shop page: auto-submit the sort dropdown
//   3) Product gallery: thumbnail switching + hover zoom
//   4) Product variants: size + colour → stock, quantity, buttons

document.addEventListener("DOMContentLoaded", () => {

    // ---------------------------------------------------------------
    // 1) Mobile burger menu toggle
    // ---------------------------------------------------------------
    const burger = document.getElementById("nav-burger");
    const links = document.getElementById("nav-links");

    if (burger && links) {
        const setMenu = (open) => {
            links.classList.toggle("open", open);
            burger.classList.toggle("open", open);
            burger.setAttribute("aria-expanded", String(open));
        };
        burger.addEventListener("click", () => {
            setMenu(!links.classList.contains("open"));
        });
        // Keyboard support: Escape closes the menu and returns focus to the button.
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && links.classList.contains("open")) {
                setMenu(false);
                burger.focus();
            }
        });
    }

    // ---------------------------------------------------------------
    // 2) Shop page: sort dropdown submits the form as soon as it changes
    //    (the min/max inputs belong to the same form, so they survive)
    // ---------------------------------------------------------------
    const sortSelect = document.getElementById("sort-select");
    if (sortSelect) {
        sortSelect.addEventListener("change", () => sortSelect.form.submit());
    }

    // ---------------------------------------------------------------
    // 3) Product gallery — big photo + clickable thumbnails + zoom
    // ---------------------------------------------------------------
    const mainImg = document.getElementById("pd-main-img");
    const thumbs = document.getElementById("pd-thumbs");
    const mainWrap = document.getElementById("pd-main-wrap");

    if (mainImg && thumbs) {
        // Clicking a thumbnail swaps it into the big frame.
        thumbs.addEventListener("click", (event) => {
            const thumb = event.target.closest(".pd-thumb");
            if (!thumb) return;

            mainImg.src = thumb.dataset.full;
            mainImg.alt = thumb.dataset.alt || mainImg.alt;

            thumbs.querySelectorAll(".pd-thumb").forEach((t) => t.classList.remove("active"));
            thumb.classList.add("active");
        });
    }

    if (mainImg && mainWrap) {
        // Subtle zoom that follows the cursor (desktop only, pointer devices).
        const canHover = window.matchMedia("(hover: hover)").matches;
        if (canHover) {
            mainWrap.addEventListener("mousemove", (event) => {
                const rect = mainWrap.getBoundingClientRect();
                const x = ((event.clientX - rect.left) / rect.width) * 100;
                const y = ((event.clientY - rect.top) / rect.height) * 100;
                mainImg.style.transformOrigin = `${x}% ${y}%`;
                mainWrap.classList.add("zoom");
            });
            mainWrap.addEventListener("mouseleave", () => {
                mainWrap.classList.remove("zoom");
                mainImg.style.transformOrigin = "center center";
            });
        }
    }

    // ---------------------------------------------------------------
    // 4) Variants: size + colour together decide the stock
    // ---------------------------------------------------------------
    const layout = document.getElementById("pd-layout");
    const sizeOptions = document.getElementById("size-options");
    const colourOptions = document.getElementById("colour-options");
    const stockLine = document.getElementById("pd-stock");
    const qtyInput = document.getElementById("qty-input");
    const qtyMinus = document.getElementById("qty-minus");
    const qtyPlus = document.getElementById("qty-plus");
    const addBtn = document.getElementById("add-to-cart-btn");
    const addForm = document.getElementById("add-to-cart-form");
    const cartVariantId = document.getElementById("cart-variant-id");
    const cartQty = document.getElementById("cart-qty");
    const waBtn = document.getElementById("whatsapp-btn");

    if (layout && sizeOptions && colourOptions && qtyInput) {
        // Variant data comes from the server as JSON:
        // [{id, size, colour, stock}, …]
        let variants = [];
        try {
            variants = JSON.parse(layout.dataset.variants || "[]");
        } catch (error) {
            variants = [];
        }

        const waNumber = layout.dataset.whatsapp || "";
        const productName = layout.dataset.productName || "";
        const productPrice = layout.dataset.productPrice || "";
        const pageUrl = layout.dataset.url || window.location.href;

        // Whole-product stock — if it is 0 the page stays "Out of stock".
        const totalStock = variants.reduce((sum, v) => sum + v.stock, 0);

        let selectedSize = null;
        let selectedColour = null;

        const variantFor = (size, colour) =>
            variants.find((v) => v.size === size && v.colour === colour);

        // A combination counts only if that exact variant exists and has stock.
        const inStock = (size, colour) => {
            const variant = variantFor(size, colour);
            return Boolean(variant && variant.stock > 0);
        };

        // --- quantity stepper ---
        const minQty = 1;
        const maxQty = () => parseInt(qtyInput.max, 10) || 1;

        const clampQty = (value) => Math.min(maxQty(), Math.max(minQty, value));

        const refreshQtyButtons = () => {
            const current = parseInt(qtyInput.value, 10) || minQty;
            qtyMinus.disabled = current <= minQty;
            qtyPlus.disabled = current >= maxQty();
        };

        qtyMinus.addEventListener("click", () => {
            qtyInput.value = clampQty((parseInt(qtyInput.value, 10) || minQty) - 1);
            refreshQtyButtons();
        });
        qtyPlus.addEventListener("click", () => {
            qtyInput.value = clampQty((parseInt(qtyInput.value, 10) || minQty) + 1);
            refreshQtyButtons();
        });
        qtyInput.addEventListener("change", () => {
            qtyInput.value = clampQty(parseInt(qtyInput.value, 10) || minQty);
            refreshQtyButtons();
        });

        // --- repaint everything from the current selection ---
        const update = () => {
            // Sizes: with a colour picked, only sizes in stock for it stay clickable.
            sizeOptions.querySelectorAll(".size-btn").forEach((btn) => {
                const size = btn.dataset.size;
                const ok = selectedColour
                    ? inStock(size, selectedColour)
                    : variants.some((v) => v.size === size && v.stock > 0);
                btn.disabled = !ok;
                if (!ok && selectedSize === size) {
                    selectedSize = null;
                    btn.classList.remove("selected");
                    btn.setAttribute("aria-pressed", "false");
                }
                btn.classList.toggle("selected", selectedSize === size);
                btn.setAttribute("aria-pressed", String(selectedSize === size));
            });

            // Colours: with a size picked, only colours in stock for it stay clickable.
            colourOptions.querySelectorAll(".colour-btn").forEach((btn) => {
                const colour = btn.dataset.colour;
                const ok = selectedSize
                    ? inStock(selectedSize, colour)
                    : variants.some((v) => v.colour === colour && v.stock > 0);
                btn.disabled = !ok;
                if (!ok && selectedColour === colour) {
                    selectedColour = null;
                    btn.classList.remove("selected");
                    btn.setAttribute("aria-pressed", "false");
                }
                btn.classList.toggle("selected", selectedColour === colour);
                btn.setAttribute("aria-pressed", String(selectedColour === colour));
            });

            const variant =
                selectedSize && selectedColour
                    ? variantFor(selectedSize, selectedColour)
                    : null;

            // Stock line for the chosen variant.
            if (stockLine) {
                if (variant) {
                    if (variant.stock > 0) {
                        stockLine.textContent = `In stock (${variant.stock} available)`;
                        stockLine.classList.add("in-stock");
                        stockLine.classList.remove("out-of-stock");
                    } else {
                        stockLine.textContent = "Out of stock";
                        stockLine.classList.add("out-of-stock");
                        stockLine.classList.remove("in-stock");
                    }
                } else if (totalStock === 0) {
                    stockLine.textContent = "Out of stock";
                    stockLine.classList.add("out-of-stock");
                    stockLine.classList.remove("in-stock");
                } else {
                    stockLine.textContent = "Select size and colour to check stock";
                    stockLine.classList.add("in-stock");
                    stockLine.classList.remove("out-of-stock");
                }
            }

            // Quantity can never exceed the selected variant's stock.
            const stock = variant ? variant.stock : 0;
            qtyInput.max = String(stock > 0 ? stock : 1);
            qtyInput.value = String(clampQty(parseInt(qtyInput.value, 10) || minQty));
            refreshQtyButtons();

            // Both action buttons stay disabled until size + colour are chosen.
            const ready = Boolean(variant && variant.stock > 0);
            if (addBtn) addBtn.disabled = !ready;
            if (waBtn) waBtn.disabled = !ready || !waNumber;

            // Keep the hidden Add-to-Cart fields in sync with the selection.
            if (cartVariantId) cartVariantId.value = ready ? String(variant.id) : "";
            if (cartQty) cartQty.value = qtyInput.value || "1";
        };

        sizeOptions.addEventListener("click", (event) => {
            const btn = event.target.closest(".size-btn");
            if (!btn || btn.disabled) return;
            selectedSize = btn.dataset.size;
            update();
        });

        colourOptions.addEventListener("click", (event) => {
            const btn = event.target.closest(".colour-btn");
            if (!btn || btn.disabled) return;
            selectedColour = btn.dataset.colour;
            update();
        });

        // --- Add to Cart: the hidden fields are synced in update();
        //     this guard only blocks submits with no variant selected.
        //     (The button is type=submit — the browser posts the form.) ---
        if (addBtn && addForm) {
            addForm.addEventListener("submit", (event) => {
                if (cartVariantId && cartVariantId.value === "") {
                    event.preventDefault();
                    return;
                }
                if (cartQty) cartQty.value = qtyInput.value || "1";
                // Friendly loading state — the server round-trip can take a moment.
                addBtn.disabled = true;
                addBtn.textContent = "Adding…";
            });
        }

        // --- Order on WhatsApp: prefilled wa.me message ---
        if (waBtn) {
            waBtn.addEventListener("click", () => {
                if (waBtn.disabled) return;
                const quantity = qtyInput.value || "1";
                const message = [
                    "Hi! I would like to order:",
                    `Product: ${productName}`,
                    `Size: ${selectedSize}`,
                    `Colour: ${selectedColour}`,
                    `Quantity: ${quantity}`,
                    `Price: ${productPrice}`,
                    `Link: ${pageUrl}`,
                ].join("\n");
                const target = `https://wa.me/${waNumber}?text=${encodeURIComponent(message)}`;
                window.open(target, "_blank", "noopener");
            });
        }

        update();   // paint the initial state
    }

    // ---------------------------------------------------------------
    // 5) Contact form — friendly "Sending…" loading state
    // ---------------------------------------------------------------
    const contactForm = document.getElementById("contact-form");
    if (contactForm) {
        contactForm.addEventListener("submit", () => {
            const btn = contactForm.querySelector("[type=submit]");
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Sending…";
            }
        });
    }
});
