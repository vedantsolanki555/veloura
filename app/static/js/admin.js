// Veloura admin JS — mobile sidebar drawer.
// Loaded by app/templates/admin/base.html (kept out of the HTML so the
// Content-Security-Policy can disallow inline scripts).
document.addEventListener("DOMContentLoaded", function () {
    var burger = document.getElementById("admin-burger");
    var sidebar = document.getElementById("admin-sidebar");
    var overlay = document.getElementById("admin-overlay");
    if (!burger || !sidebar) return;

    function toggle(open) {
        sidebar.classList.toggle("open", open);
        if (overlay) overlay.classList.toggle("visible", open);
        burger.setAttribute("aria-expanded", String(open));
    }

    burger.addEventListener("click", function () {
        toggle(!sidebar.classList.contains("open"));
    });
    if (overlay) {
        overlay.addEventListener("click", function () { toggle(false); });
    }
    // Keyboard: Escape closes the drawer and returns focus to the button.
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && sidebar.classList.contains("open")) {
            toggle(false);
            burger.focus();
        }
    });
});

// ---- Confirm dialog before any form with data-confirm submits ----
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.getAttribute("data-confirm"))) {
                event.preventDefault();
            }
        });
    });
});

// ---- Product form: variants editor + slug preview ----
document.addEventListener("DOMContentLoaded", function () {
    var rowsBox = document.getElementById("variant-rows");
    var addBtn = document.getElementById("add-variant-btn");

    if (rowsBox && addBtn) {
        // Existing variants come from the server as JSON in data-variants.
        var existing = [];
        try {
            existing = JSON.parse(rowsBox.getAttribute("data-variants") || "[]");
        } catch (error) {
            existing = [];
        }

        function escapeHtml(text) {
            return String(text)
                .replace(/&/g, "&amp;").replace(/</g, "&lt;")
                .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
        }

        function makeRow(data) {
            data = data || {};
            var row = document.createElement("div");
            row.className = "variant-row";
            // Every input posts a value in the same list — the server zips them
            // together by index (see _parse_variants_from_request in admin.py).
            row.innerHTML =
                '<input type="hidden" name="variant_id" value="' + (data.id || "") + '">' +
                '<input type="text" name="variant_size" placeholder="Size (M, L, Free…)" ' +
                'value="' + escapeHtml(data.size || "") + '" maxlength="20" required>' +
                '<input type="text" name="variant_colour" placeholder="Colour (Indigo…)" ' +
                'value="' + escapeHtml(data.colour || "") + '" maxlength="50" required>' +
                '<input type="number" name="variant_stock" placeholder="Stock" min="0" step="1" ' +
                'value="' + (data.stock != null ? data.stock : "") + '" required>' +
                '<button type="button" class="btn-mini btn-mini-danger remove-variant">✕</button>';
            row.querySelector(".remove-variant").addEventListener("click", function () {
                row.remove();
            });
            return row;
        }

        existing.forEach(function (v) { rowsBox.appendChild(makeRow(v)); });
        // A new product starts with one blank row so the form is never empty.
        if (existing.length === 0) rowsBox.appendChild(makeRow());

        addBtn.addEventListener("click", function () {
            rowsBox.appendChild(makeRow());
        });
    }

    // Slug preview: auto-fill slug from the name until the admin edits it.
    var nameField = document.getElementById("field-name");
    var slugField = document.getElementById("field-slug");
    if (nameField && slugField) {
        var touchedByAdmin = slugField.value !== "";
        slugField.addEventListener("input", function () { touchedByAdmin = true; });

        nameField.addEventListener("input", function () {
            if (touchedByAdmin) return;
            slugField.value = nameField.value.toLowerCase()
                .replace(/'/g, "")
                .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
        });
    }
});
