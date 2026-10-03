(function () {
    const root = document.getElementById("sales-desk");
    if (!root) return;

    const urls = {
        productSearch: root.dataset.productSearchUrl,
        cartAdd: root.dataset.cartAddUrl,
        cartQtyTemplate: root.dataset.cartQtyUrlTemplate,
        cartRemoveTemplate: root.dataset.cartRemoveUrlTemplate,
        tintCalculate: root.dataset.tintCalculateUrl,
        tintAdd: root.dataset.tintAddUrl,
        paymentAdd: root.dataset.paymentAddUrl,
        desk: root.dataset.deskUrl,
    };

    const cartPanel = document.getElementById("cart-panel");
    const tintingPanel = document.getElementById("tinting-panel");
    const tintingModal = document.getElementById("tinting-modal");

    function openTintingModal() {
        if (!tintingModal) return;
        tintingModal.classList.remove("hidden");
        tintingModal.classList.add("flex");
    }

    function closeTintingModal() {
        if (!tintingModal) return;
        tintingModal.classList.add("hidden");
        tintingModal.classList.remove("flex");
        const scanner = document.getElementById("scanner-input");
        if (scanner) scanner.focus();
    }

    function debounce(fn, wait) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), wait);
        };
    }

    function itemUrl(template, itemId) {
        return template.replace("/0/", `/${itemId}/`);
    }

    function setCartError(message) {
        const el = document.getElementById("cart-error");
        if (el) el.textContent = message || "";
    }

    function swapCart(html) {
        cartPanel.innerHTML = html;
        const scanner = document.getElementById("scanner-input");
        if (scanner) scanner.focus();
    }

    function swapTinting(html) {
        tintingPanel.innerHTML = html;
    }

    async function postForm(url, data) {
        return chromaposFetchJSON(url, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams(data),
        });
    }

    async function getJSON(url, params) {
        const qs = new URLSearchParams(params).toString();
        return chromaposFetchJSON(`${url}?${qs}`);
    }

    // ---------- Cart: scanner add ----------
    async function handleScanAdd() {
        const input = document.getElementById("scanner-input");
        if (!input) return;
        const sku = input.value.trim();
        if (!sku) return;
        try {
            const data = await postForm(urls.cartAdd, { sku });
            swapCart(data.html);
            if (!data.success) setCartError(data.error);
            document.getElementById("scanner-suggestions").innerHTML = "";
        } catch (err) {
            setCartError(err.message);
        }
    }

    const runProductSearch = debounce(async (query) => {
        const box = document.getElementById("scanner-suggestions");
        if (!box) return;
        if (!query) {
            box.innerHTML = "";
            return;
        }
        try {
            const data = await getJSON(urls.productSearch, { q: query });
            box.innerHTML = data.results
                .map(
                    (p) => `
                <button type="button" data-action="pick-suggestion" data-sku="${p.sku}"
                        class="w-full text-left px-sm py-xs rounded-lg border border-outline-variant bg-surface-container-lowest hover:bg-surface-container transition-colors flex justify-between items-center">
                    <span class="font-body-md text-[13px] text-on-surface truncate">${p.name} <span class="text-secondary">(${p.sku})</span></span>
                    <span class="font-mono-data text-[13px] text-on-surface">$${p.unit_price}</span>
                </button>`
                )
                .join("");
        } catch (err) {
            /* ignore search errors */
        }
    }, 250);

    // ---------- Cart: qty / remove ----------
    async function handleQty(el) {
        const itemId = el.dataset.itemId;
        const delta = el.dataset.delta;
        try {
            const data = await postForm(itemUrl(urls.cartQtyTemplate, itemId), { delta });
            swapCart(data.html);
            if (!data.success) setCartError(data.error);
        } catch (err) {
            setCartError(err.message);
        }
    }

    async function handleRemove(el) {
        const itemId = el.dataset.itemId;
        try {
            const data = await postForm(itemUrl(urls.cartRemoveTemplate, itemId), {});
            swapCart(data.html);
        } catch (err) {
            setCartError(err.message);
        }
    }

    // ---------- Payment ----------
    function handleShowPayment(el) {
        const method = el.dataset.method;
        const cashForm = document.getElementById("cash-payment-form");
        const cardForm = document.getElementById("card-payment-form");
        if (!cashForm || !cardForm) return;
        if (method === "cash") {
            cashForm.classList.toggle("hidden");
            cardForm.classList.add("hidden");
        } else {
            cardForm.classList.toggle("hidden");
            cashForm.classList.add("hidden");
        }
    }

    async function handlePay(el) {
        const method = el.dataset.method;
        const payload = { method };
        if (method === "cash") {
            const tendered = document.getElementById("cash-tendered").value;
            payload.tendered = tendered;
        } else if (method === "card") {
            const amount = document.getElementById("card-amount").value;
            if (amount) payload.amount = amount;
        }
        try {
            const data = await postForm(urls.paymentAdd, payload);
            if (data.completed) {
                window.location.assign(data.redirect_url || urls.desk);
                return;
            }
            swapCart(data.html);
            if (!data.success) setCartError(data.error);
        } catch (err) {
            setCartError(err.message);
        }
    }

    // ---------- Discounts ----------
    function toggleOrderDiscountForm() {
        const form = document.getElementById("order-discount-form");
        if (!form) return;
        form.classList.toggle("hidden");
        if (!form.classList.contains("hidden")) {
            const value = document.getElementById("order-discount-value");
            if (value) value.focus();
        }
    }

    async function postOrderDiscount(payload) {
        const totals = document.getElementById("totals-area");
        if (!totals) return;
        try {
            const data = await postForm(totals.dataset.discountUrl, payload);
            swapCart(data.html);
            if (!data.success) setCartError(data.error);
        } catch (err) {
            setCartError(err.message);
        }
    }

    function applyOrderDiscount() {
        const type = document.getElementById("order-discount-type");
        const value = document.getElementById("order-discount-value");
        const reason = document.getElementById("order-discount-reason");
        if (!type || !value) return;
        return postOrderDiscount({
            discount_type: type.value,
            discount_value: value.value,
            reason: reason ? reason.value : "",
        });
    }

    function applyQuickDiscount(el) {
        const reason = document.getElementById("order-discount-reason");
        return postOrderDiscount({
            discount_type: "percent",
            discount_value: el.dataset.percent,
            reason: reason ? reason.value : "",
        });
    }

    function clearOrderDiscount() {
        return postOrderDiscount({ discount_type: "none" });
    }

    function toggleItemDiscount(el) {
        const row = document.getElementById(`item-discount-${el.dataset.itemId}`);
        if (!row) return;
        row.classList.toggle("hidden");
        if (!row.classList.contains("hidden")) {
            const input = row.querySelector('[data-role="item-discount-value"]');
            if (input) input.focus();
        }
    }

    async function postItemDiscount(itemId, payload) {
        const template = root.dataset.itemDiscountUrlTemplate;
        try {
            const data = await postForm(itemUrl(template, itemId), payload);
            swapCart(data.html);
            if (!data.success) setCartError(data.error);
        } catch (err) {
            setCartError(err.message);
        }
    }

    function applyItemDiscount(el) {
        const itemId = el.dataset.itemId;
        const row = document.getElementById(`item-discount-${itemId}`);
        if (!row) return;
        const type = row.querySelector('[data-role="item-discount-type"]');
        const value = row.querySelector('[data-role="item-discount-value"]');
        return postItemDiscount(itemId, {
            discount_type: type ? type.value : "percent",
            discount_value: value ? value.value : "0",
        });
    }

    function clearItemDiscount(el) {
        return postItemDiscount(el.dataset.itemId, { discount_type: "none" });
    }

    // ---------- Customer attach ----------
    const customerArea = document.getElementById("customer-area");

    async function attachCustomer(customerId) {
        try {
            const data = await postForm(customerArea.dataset.attachUrl, { customer_id: customerId || "" });
            swapCart(data.html);
        } catch (err) {
            setCartError(err.message);
        }
    }

    function showWalkinForm() {
        const form = document.getElementById("walkin-form");
        if (!form) return;
        form.classList.toggle("hidden");
        const input = document.getElementById("walkin-name");
        if (input && !form.classList.contains("hidden")) input.focus();
    }

    async function saveWalkin() {
        const area = document.getElementById("customer-area");
        const input = document.getElementById("walkin-name");
        if (!area || !input) return;
        const name = input.value.trim();
        if (!name) {
            setCartError("Enter a name for the walk-in customer.");
            return;
        }
        try {
            const data = await postForm(area.dataset.walkinUrl, { name });
            swapCart(data.html);
            if (!data.success) setCartError(data.error);
        } catch (err) {
            setCartError(err.message);
        }
    }

    const runCustomerSearch = debounce(async (query) => {
        const box = document.getElementById("customer-search-results");
        if (!box || !customerArea) return;
        if (!query) {
            box.innerHTML = "";
            box.classList.add("hidden");
            return;
        }
        try {
            const data = await getJSON(customerArea.dataset.searchUrl, { q: query });
            if (!data.results.length) {
                box.innerHTML = '<div class="p-sm text-secondary font-body-md text-[12px]">No matches.</div>';
            } else {
                box.innerHTML = data.results
                    .map(
                        (c) => `
                    <button type="button" data-action="pick-customer" data-customer-id="${c.id}"
                            class="w-full text-left px-sm py-2 hover:bg-surface-container-low transition-colors flex justify-between items-center">
                        <span class="font-body-md text-[13px] text-on-surface truncate">${c.name}</span>
                        <span class="font-mono-data text-[11px] text-secondary">${c.phone || ""}</span>
                    </button>`
                    )
                    .join("");
            }
            box.classList.remove("hidden");
        } catch (err) {
            /* ignore transient search errors */
        }
    }, 250);

    // ---------- Tinting desk ----------
    function collectTintParams() {
        const get = (id) => document.getElementById(id);
        const activeSize = tintingPanel.querySelector('[data-field="base_size"][data-active="true"]');
        return {
            product_id: get("base-product-select") ? get("base-product-select").value : "",
            base_size: activeSize ? activeSize.dataset.value : "4L",
            hex: get("hex-input") ? get("hex-input").value : "",
            r: get("r-input") ? get("r-input").value : 255,
            g: get("g-input") ? get("g-input").value : 255,
            b: get("b-input") ? get("b-input").value : 255,
            name: get("formula-name-input") ? get("formula-name-input").value : "",
            finish: get("finish-select") ? get("finish-select").value : "",
            shade_id: get("shade-id-input") ? get("shade-id-input").value : "",
        };
    }

    async function recalcTint() {
        try {
            const data = await getJSON(urls.tintCalculate, collectTintParams());
            swapTinting(data.html);
        } catch (err) {
            /* silently ignore transient calc errors */
        }
    }
    const recalcTintDebounced = debounce(recalcTint, 300);

    function hexToRgb(hex) {
        const clean = hex.replace("#", "").padEnd(6, "0").slice(0, 6);
        const num = parseInt(clean, 16);
        if (Number.isNaN(num)) return null;
        return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
    }

    function rgbToHex(r, g, b) {
        return [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("").toUpperCase();
    }

    function syncSwatch(hex) {
        const swatch = document.getElementById("color-swatch");
        const readout = document.getElementById("hex-readout");
        if (swatch) swatch.style.backgroundColor = `#${hex}`;
        if (readout) readout.textContent = `#${hex}`;
    }

    function handleHexInput(el) {
        const rgb = hexToRgb(el.value);
        if (rgb) {
            document.getElementById("r-input").value = rgb.r;
            document.getElementById("g-input").value = rgb.g;
            document.getElementById("b-input").value = rgb.b;
            syncSwatch(el.value.replace("#", "").toUpperCase());
        }
        recalcTintDebounced();
    }

    function handleRgbInput() {
        const r = parseInt(document.getElementById("r-input").value, 10) || 0;
        const g = parseInt(document.getElementById("g-input").value, 10) || 0;
        const b = parseInt(document.getElementById("b-input").value, 10) || 0;
        const hex = rgbToHex(r, g, b);
        document.getElementById("hex-input").value = hex;
        syncSwatch(hex);
        recalcTintDebounced();
    }

    function hsvToRgb(h, s, v) {
        const c = v * s;
        const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
        const m = v - c;
        let rp, gp, bp;
        if (h < 60) [rp, gp, bp] = [c, x, 0];
        else if (h < 120) [rp, gp, bp] = [x, c, 0];
        else if (h < 180) [rp, gp, bp] = [0, c, x];
        else if (h < 240) [rp, gp, bp] = [0, x, c];
        else if (h < 300) [rp, gp, bp] = [x, 0, c];
        else [rp, gp, bp] = [c, 0, x];
        return { r: (rp + m) * 255, g: (gp + m) * 255, b: (bp + m) * 255 };
    }

    function handleWheelClick(wheel, event) {
        const rect = wheel.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dx = event.clientX - cx;
        const dy = event.clientY - cy;
        let angle = (Math.atan2(dy, dx) * 180) / Math.PI + 90;
        if (angle < 0) angle += 360;
        const { r, g, b } = hsvToRgb(angle, 1, 1);
        document.getElementById("r-input").value = Math.round(r);
        document.getElementById("g-input").value = Math.round(g);
        document.getElementById("b-input").value = Math.round(b);
        const hex = rgbToHex(r, g, b);
        document.getElementById("hex-input").value = hex;
        syncSwatch(hex);
        recalcTintDebounced();
    }

    function resetTintForm() {
        const hexInput = document.getElementById("hex-input");
        const rInput = document.getElementById("r-input");
        const gInput = document.getElementById("g-input");
        const bInput = document.getElementById("b-input");
        const nameInput = document.getElementById("formula-name-input");
        const shadeIdInput = document.getElementById("shade-id-input");
        if (hexInput) hexInput.value = "FFFFFF";
        if (rInput) rInput.value = 255;
        if (gInput) gInput.value = 255;
        if (bInput) bInput.value = 255;
        if (nameInput) nameInput.value = "";
        if (shadeIdInput) shadeIdInput.value = "";
        syncSwatch("FFFFFF");
        recalcTint();
    }

    async function handleTintAdd() {
        try {
            const data = await postForm(urls.tintAdd, collectTintParams());
            swapCart(data.html);
            if (!data.success) {
                setCartError(data.error);
            } else {
                resetTintForm();
                closeTintingModal();
            }
        } catch (err) {
            setCartError(err.message);
        }
    }

    // ---------- Delegated events ----------
    document.addEventListener("click", (e) => {
        const actionEl = e.target.closest("[data-action]");
        if (actionEl) {
            const action = actionEl.dataset.action;
            if (action === "scan-add") return handleScanAdd();
            if (action === "pick-suggestion") {
                document.getElementById("scanner-input").value = actionEl.dataset.sku;
                document.getElementById("scanner-suggestions").innerHTML = "";
                return handleScanAdd();
            }
            if (action === "qty") return handleQty(actionEl);
            if (action === "remove") return handleRemove(actionEl);
            if (action === "pick-customer") return attachCustomer(actionEl.dataset.customerId);
            if (action === "detach-customer") return attachCustomer("");
            if (action === "show-walkin") return showWalkinForm();
            if (action === "save-walkin") return saveWalkin();
            if (action === "toggle-order-discount") return toggleOrderDiscountForm();
            if (action === "apply-order-discount") return applyOrderDiscount();
            if (action === "quick-discount") return applyQuickDiscount(actionEl);
            if (action === "clear-order-discount") return clearOrderDiscount();
            if (action === "toggle-item-discount") return toggleItemDiscount(actionEl);
            if (action === "apply-item-discount") return applyItemDiscount(actionEl);
            if (action === "clear-item-discount") return clearItemDiscount(actionEl);
            if (action === "show-payment") return handleShowPayment(actionEl);
            if (action === "pay") return handlePay(actionEl);
            if (action === "tint-add") return handleTintAdd();
            if (action === "open-tinting") return openTintingModal();
            if (action === "close-tinting") return closeTintingModal();
            if (action === "tint-control" && actionEl.tagName === "BUTTON") {
                tintingPanel.querySelectorAll('[data-field="base_size"]').forEach((btn) => (btn.dataset.active = "false"));
                actionEl.dataset.active = "true";
                return recalcTint();
            }
            return;
        }
        if (e.target === tintingModal) return closeTintingModal();
        const wheel = e.target.closest("#color-wheel");
        if (wheel) return handleWheelClick(wheel, e);
    });

    document.addEventListener("keydown", (e) => {
        if (e.target && e.target.id === "scanner-input" && e.key === "Enter") {
            e.preventDefault();
            handleScanAdd();
            return;
        }
        if (e.key === "Enter" && e.target && e.target.id === "walkin-name") {
            e.preventDefault();
            saveWalkin();
            return;
        }
        if (e.key === "Enter" && e.target && (e.target.id === "order-discount-value" || e.target.id === "order-discount-reason")) {
            e.preventDefault();
            applyOrderDiscount();
            return;
        }
        if (e.key === "Enter" && e.target && e.target.dataset && e.target.dataset.role === "item-discount-value") {
            e.preventDefault();
            const row = e.target.closest("[data-item-discount]");
            if (row) postItemDiscount(row.dataset.itemDiscount, {
                discount_type: (row.querySelector('[data-role="item-discount-type"]') || {}).value || "percent",
                discount_value: e.target.value,
            });
            return;
        }
        if (e.key === "Escape" && tintingModal && !tintingModal.classList.contains("hidden")) {
            closeTintingModal();
        }
    });

    if (root.dataset.autoOpenTint === "1") {
        openTintingModal();
    }

    document.addEventListener("input", (e) => {
        if (e.target.id === "scanner-input") {
            runProductSearch(e.target.value.trim());
            return;
        }
        if (e.target.id === "customer-search-input") {
            runCustomerSearch(e.target.value.trim());
            return;
        }
        const el = e.target.closest('[data-action="tint-control"]');
        if (!el) return;
        const field = el.dataset.field;
        if (field === "hex") return handleHexInput(el);
        if (field === "r" || field === "g" || field === "b") return handleRgbInput();
        if (field === "name") return recalcTintDebounced();
    });

    document.addEventListener("change", (e) => {
        const el = e.target.closest('[data-action="tint-control"]');
        if (!el) return;
        const field = el.dataset.field;
        if (field === "product_id" || field === "finish") return recalcTint();
    });
})();
