// ChromaPOS shared front-end helpers.
// Page-specific logic (cart, tinting desk, inventory transfers, etc.)
// lives in per-screen scripts loaded via {% block extra_scripts %}.

function chromaposCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

async function chromaposFetchJSON(url, options = {}) {
    const opts = Object.assign({}, options);
    opts.headers = Object.assign(
        { 'X-CSRFToken': chromaposCsrfToken() },
        opts.headers || {}
    );
    const response = await fetch(url, opts);
    if (!response.ok) {
        let detail = '';
        try { detail = (await response.json()).error || ''; } catch (e) { /* ignore */ }
        throw new Error(detail || `Request failed: ${response.status}`);
    }
    return response.json();
}

// Global search — bound to every ".js-global-search" instance on the page
// (there's one inline in the desktop header and a second full-width one in
// the mobile search row; both share this logic via data-role attributes).
document.querySelectorAll('.js-global-search').forEach((wrapper) => {
    const input = wrapper.querySelector('[data-role="search-input"]');
    const results = wrapper.querySelector('[data-role="search-results"]');
    const searchUrl = wrapper.dataset.searchUrl;
    if (!input || !results || !searchUrl) return;

    let debounceTimer;
    function renderResults(data) {
        if (!data.products.length && !data.customers.length) {
            results.innerHTML = '<div class="p-md text-secondary font-body-md text-[13px]">No matches.</div>';
            results.classList.remove('hidden');
            return;
        }
        let html = '';
        if (data.products.length) {
            html += '<div class="px-md pt-sm pb-1 font-label-md text-[11px] text-secondary uppercase tracking-wider">Products</div>';
            html += data.products.map((p) => `
                <a href="${p.url}" class="flex justify-between items-center px-md py-sm hover:bg-surface-container-low transition-colors">
                    <span class="font-body-md text-[13px] text-on-surface truncate">${p.name}</span>
                    <span class="font-mono-data text-[12px] text-secondary">${p.sku}</span>
                </a>`).join('');
        }
        if (data.customers.length) {
            html += '<div class="px-md pt-sm pb-1 font-label-md text-[11px] text-secondary uppercase tracking-wider">Customers</div>';
            html += data.customers.map((c) => `
                <a href="${c.url}" class="flex justify-between items-center px-md py-sm hover:bg-surface-container-low transition-colors">
                    <span class="font-body-md text-[13px] text-on-surface truncate">${c.name}</span>
                    <span class="font-mono-data text-[12px] text-secondary">${c.phone || ''}</span>
                </a>`).join('');
        }
        results.innerHTML = html;
        results.classList.remove('hidden');
    }

    input.addEventListener('input', () => {
        const q = input.value.trim();
        clearTimeout(debounceTimer);
        if (!q) {
            results.classList.add('hidden');
            return;
        }
        debounceTimer = setTimeout(async () => {
            try {
                const data = await chromaposFetchJSON(`${searchUrl}?q=${encodeURIComponent(q)}`);
                renderResults(data);
            } catch (err) { /* ignore transient search errors */ }
        }, 250);
    });

    document.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) results.classList.add('hidden');
    });
});

// Mobile nav drawer + mobile search row.
(function () {
    const nav = document.getElementById('mobile-nav');
    const backdrop = document.getElementById('mobile-nav-backdrop');
    const navToggle = document.getElementById('mobile-nav-toggle');
    const navClose = document.getElementById('mobile-nav-close');
    const searchToggle = document.getElementById('mobile-search-toggle');
    const searchRow = document.getElementById('mobile-search-row');
    if (!nav || !backdrop) return;

    const MOBILE_BREAKPOINT = 768; // matches Tailwind's `md`

    function openNav() {
        nav.classList.remove('-translate-x-full');
        nav.classList.add('translate-x-0');
        backdrop.classList.remove('hidden');
        navToggle && navToggle.setAttribute('aria-expanded', 'true');
    }
    function closeNav() {
        nav.classList.add('-translate-x-full');
        nav.classList.remove('translate-x-0');
        backdrop.classList.add('hidden');
        navToggle && navToggle.setAttribute('aria-expanded', 'false');
    }
    function closeSearchRow() {
        if (!searchRow) return;
        searchRow.classList.add('hidden');
        searchToggle && searchToggle.setAttribute('aria-expanded', 'false');
    }
    function toggleSearchRow() {
        if (!searchRow) return;
        const opening = searchRow.classList.contains('hidden');
        searchRow.classList.toggle('hidden');
        searchToggle && searchToggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
        if (opening) {
            const input = searchRow.querySelector('[data-role="search-input"]');
            input && input.focus();
        }
    }

    navToggle && navToggle.addEventListener('click', openNav);
    navClose && navClose.addEventListener('click', closeNav);
    backdrop.addEventListener('click', closeNav);
    searchToggle && searchToggle.addEventListener('click', () => {
        closeNav();
        toggleSearchRow();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        closeNav();
        closeSearchRow();
    });
    window.addEventListener('resize', () => {
        if (window.innerWidth >= MOBILE_BREAKPOINT) {
            closeNav();
            closeSearchRow();
        }
    });
})();
