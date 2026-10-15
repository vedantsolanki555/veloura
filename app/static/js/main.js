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
});
