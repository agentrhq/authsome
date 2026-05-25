(() => {
    const ready = (fn) =>
        document.readyState === "loading"
            ? document.addEventListener("DOMContentLoaded", fn)
            : fn();

    function initSearchAndFilter() {
        const grid = document.getElementById("connectionList") || document.getElementById("appGrid");
        const search = document.getElementById("appSearch");
        const empty = document.getElementById("appEmpty");
        if (!grid) return;

        let activeFilter = "all";
        const cards = Array.from(grid.querySelectorAll(".app-card, .connection-row"));

        const applyFilters = () => {
            const q = (search?.value || "").trim().toLowerCase();
            let visible = 0;
            cards.forEach((card) => {
                const matchesQuery = !q || card.dataset.name.includes(q);
                const status = card.dataset.status;
                const matchesFilter =
                    !document.querySelector(".filter-pill") ||
                    activeFilter === "all" ||
                    (activeFilter === "connected" && status !== "available") ||
                    (activeFilter === "available" && status === "available");
                const show = matchesQuery && matchesFilter;
                card.classList.toggle("hidden", !show);
                if (show) visible += 1;
            });
            if (empty) empty.classList.toggle("hidden", visible !== 0);
        };

        document.querySelectorAll(".filter-pill").forEach((pill) => {
            pill.addEventListener("click", () => {
                document
                    .querySelectorAll(".filter-pill")
                    .forEach((p) => p.classList.remove("active"));
                pill.classList.add("active");
                activeFilter = pill.dataset.filter || "all";
                applyFilters();
            });
        });

        if (search) search.addEventListener("input", applyFilters);
    }

    function initSecretToggles() {
        document.querySelectorAll("[data-toggle-secret]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const row = btn.closest(".field-row");
                const target = row?.querySelector("[data-secret]");
                if (!target) return;
                const real = target.dataset.secretValue;
                if (!real) return;
                const isMasked = target.classList.contains("mask");
                if (isMasked) {
                    target.dataset.maskedDisplay = target.textContent;
                    target.textContent = real;
                    target.classList.remove("mask");
                } else {
                    target.textContent = target.dataset.maskedDisplay || "••••••••••••••••";
                    target.classList.add("mask");
                }
            });
        });
    }

    function initCopyButtons() {
        document.querySelectorAll("[data-copy]").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const value = btn.dataset.copy;
                if (!value) return;
                try {
                    await navigator.clipboard.writeText(value);
                    const original = btn.title;
                    btn.title = "Copied";
                    btn.classList.add("active");
                    setTimeout(() => {
                        btn.title = original;
                        btn.classList.remove("active");
                    }, 900);
                } catch {
                    /* clipboard write failed; nothing fatal to do here */
                }
            });
        });
    }

    function initLoginModal() {
        const modal = document.getElementById("loginModal");
        const form = document.getElementById("loginModalForm");
        const hiddenConnection = document.getElementById("loginConnectionName");
        const input = document.getElementById("connectionNameInput");
        if (!modal || !form || !hiddenConnection || !input) return;

        document.querySelectorAll("[data-open-login-modal]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const provider = btn.dataset.provider;
                if (!provider) return;
                form.action = `/ui/apps/${provider}/connect`;
                hiddenConnection.value = "";
                input.value = "";
                modal.showModal();
                input.focus();
            });
        });

        document.querySelectorAll("[data-close-login-modal]").forEach((btn) => {
            btn.addEventListener("click", () => modal.close());
        });

        form.addEventListener("submit", () => {
            hiddenConnection.value = input.value.trim();
        });
    }

    ready(() => {
        initSearchAndFilter();
        initSecretToggles();
        initCopyButtons();
        initLoginModal();
    });
})();
