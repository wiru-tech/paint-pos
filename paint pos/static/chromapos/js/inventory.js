(function () {
    const modal = document.getElementById("transfer-modal");
    if (!modal) return;

    document.addEventListener("click", (e) => {
        const openBtn = e.target.closest('[data-action="open-transfer"]');
        if (openBtn) {
            document.getElementById("transfer-product-id").value = openBtn.dataset.productId;
            document.getElementById("transfer-product-name").textContent = openBtn.dataset.productName;
            modal.classList.remove("hidden");
            return;
        }
        if (e.target.closest('[data-action="close-transfer"]') || e.target === modal) {
            modal.classList.add("hidden");
        }
    });
})();

(function () {
    const modal = document.getElementById("adjust-modal");
    if (!modal) return;

    document.addEventListener("click", (e) => {
        const openBtn = e.target.closest('[data-action="open-adjust"]');
        if (openBtn) {
            document.getElementById("adjust-product-id").value = openBtn.dataset.productId;
            document.getElementById("adjust-product-name").textContent = openBtn.dataset.productName;
            modal.classList.remove("hidden");
            return;
        }
        if (e.target.closest('[data-action="close-adjust"]') || e.target === modal) {
            modal.classList.add("hidden");
        }
    });
})();

(function () {
    const modal = document.getElementById("warehouse-transfer-modal");
    if (!modal) return;

    document.addEventListener("click", (e) => {
        const openBtn = e.target.closest('[data-action="open-warehouse-transfer"]');
        if (openBtn) {
            document.getElementById("warehouse-transfer-from-branch").value = openBtn.dataset.branchId;
            document.getElementById("warehouse-transfer-branch-name").textContent = `From ${openBtn.dataset.branchName}`;
            const productSelect = modal.querySelector('select[name="product_id"]');
            if (productSelect && openBtn.dataset.productId) productSelect.value = openBtn.dataset.productId;
            const toBranchSelect = modal.querySelector('select[name="to_branch"]');
            if (toBranchSelect && openBtn.dataset.toBranchId) toBranchSelect.value = openBtn.dataset.toBranchId;
            modal.classList.remove("hidden");
            return;
        }
        if (e.target.closest('[data-action="close-warehouse-transfer"]') || e.target === modal) {
            modal.classList.add("hidden");
        }
    });
})();
