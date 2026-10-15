// Veloura front-end JS (Phase 2)
// 1) Mobile burger menu toggle

document.addEventListener("DOMContentLoaded", () => {
    const burger = document.getElementById("nav-burger");
    const links = document.getElementById("nav-links");

    if (burger && links) {
        burger.addEventListener("click", () => {
            const open = links.classList.toggle("open");
            burger.classList.toggle("open", open);
            burger.setAttribute("aria-expanded", String(open));
        });
    }

    // 2) Shop page: sort dropdown — submit the form as soon as value changes
    const sortSelect = document.getElementById("sort-select");
    if (sortSelect) {
        sortSelect.addEventListener("change", () => {
            // min/max inputs are part of the same form, so they are kept.
            sortSelect.form.submit();
        });
    }

    // 3) Product detail: size buttons — highlight one at a time
    const sizeOptions = document.getElementById("size-options");
    if (sizeOptions) {
        sizeOptions.addEventListener("click", (event) => {
            const btn = event.target.closest(".size-btn");
            if (!btn || btn.disabled) return;
            sizeOptions.querySelectorAll(".size-btn").forEach((b) => {
                b.classList.remove("selected");
                b.setAttribute("aria-pressed", "false");
            });
            btn.classList.add("selected");
            btn.setAttribute("aria-pressed", "true");
        });
    }

    // 4) Product detail: quantity + / − buttons (min 1, max = stock)
    const qtyInput = document.getElementById("qty-input");
    const qtyMinus = document.getElementById("qty-minus");
    const qtyPlus = document.getElementById("qty-plus");

    if (qtyInput && qtyMinus && qtyPlus) {
        const minQty = parseInt(qtyInput.min, 10) || 1;
        const maxQty = parseInt(qtyInput.max, 10) || 99;

        function clampQty(value) {
            return Math.min(maxQty, Math.max(minQty, value));
        }

        function refreshQtyButtons() {
            const current = parseInt(qtyInput.value, 10) || minQty;
            qtyMinus.disabled = current <= minQty;
            qtyPlus.disabled = current >= maxQty;
        }

        qtyMinus.addEventListener("click", () => {
            qtyInput.value = clampQty((parseInt(qtyInput.value, 10) || minQty) - 1);
            refreshQtyButtons();
        });

        qtyPlus.addEventListener("click", () => {
            qtyInput.value = clampQty((parseInt(qtyInput.value, 10) || minQty) + 1);
            refreshQtyButtons();
        });

        // Also handle typing directly in the box.
        qtyInput.addEventListener("change", () => {
            qtyInput.value = clampQty(parseInt(qtyInput.value, 10) || minQty);
            refreshQtyButtons();
        });

        refreshQtyButtons();
    }

    // 5) Product detail: Add to Cart button — message only (real cart in Phase 4)
    const addToCartBtn = document.getElementById("add-to-cart-btn");
    const cartMsg = document.getElementById("cart-msg");
    if (addToCartBtn && cartMsg) {
        addToCartBtn.addEventListener("click", () => {
            cartMsg.hidden = false;
        });
    }
});
