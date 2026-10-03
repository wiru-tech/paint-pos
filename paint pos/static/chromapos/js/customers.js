(function () {
    const select = document.getElementById("quick-retint-select");
    if (!select) return;
    select.addEventListener("change", () => {
        document.querySelectorAll(".quick-retint-detail").forEach((el) => {
            el.style.display = el.dataset.formulaId === select.value ? "" : "none";
        });
    });
})();
