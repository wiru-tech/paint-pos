# ChromaPOS — Requirements & Feature Scope

This document lists what ChromaPOS is built to do. It reflects the actual
implementation (not aspirational marketing copy) — items marked **Planned**
are not built yet.

## 1. Overview

ChromaPOS is a point-of-sale system for a multi-branch paint retail chain,
covering checkout, custom paint tinting, multi-branch inventory, and
customer history. Built with Django (backend + server-rendered templates),
SQLite (dev database), and Tailwind CDN + vanilla JS for the frontend.

## 2. User Accounts & Access

- Staff log in with a username/password at `/accounts/login/` (Django's
  built-in auth).
- Every staff account has a `Profile` with a `role` (Cashier / Manager) and
  an assigned `Branch`. A branch assignment is required to use the Sales
  desk or see branch-scoped dashboard stats.
- All POS pages require login; anonymous visitors are redirected to sign in.
- **Planned:** enforcing the Cashier/Manager role distinction (e.g. only
  managers can edit prices or approve transfers). The role field exists
  today but every logged-in user currently has equal access.

## 3. Dashboard (Home)

- Landing page after login: greeting, branch, and date.
- Live stats: today's sales (count + $), low-stock count, out-of-stock
  count, total customers on file.
- Resume/Start Sale shortcut (reflects an in-progress cart if one exists).
- Recent Sales list and a "Needs Reordering" list, both branch-scoped.
- Quick links to Inventory and Customer History.

## 4. Sales & Tinting Desk

- **Checkout register:** SKU/barcode scan-to-add (with live search
  suggestions), quantity +/- and remove, running subtotal/tax(8%)/total,
  tied to one open `Sale` per cashier session.
- **Tinting desk:** pick a tintable base product and can size (1L/4L/20L),
  choose a color via hex/RGB fields or a clickable hue wheel, and get a
  computed pigment formula (heuristic mix against a fixed pigment set —
  not a certified color match) with a live capacity meter and overflow
  warning.
- Adding a tinted color creates a `ColorFormula` + pigment lines and adds
  one cart line (base can + tint surcharge, priced from pigment cost).
- **Checkout:** cash (tendered amount, change due) or card. Partial
  payments are supported — paying less than the balance leaves the sale
  open for a second payment (basic split-payment support). Completing a
  sale decrements branch stock and shows a printable receipt.
- **Discounts:** a whole-order discount (percent or flat amount, with a
  reason) and/or a discount on any individual cart line — both computed
  server-side and re-applied on every cart change. Cashiers are capped at
  `MAX_CASHIER_DISCOUNT_PERCENT` (default 20%) in `chromapos/settings.py`;
  managers have no cap. The cart, receipt, and reports all show the
  original price struck through next to the discounted price.
- **Walk-in customers:** a "Walk-in" button on the Sales desk records a
  name-only customer (no phone/email required) and attaches them to the
  sale in one step. Walk-ins are excluded from loyalty-point earning; the
  Customer History list has separate Regular / Walk-in filter tabs.
- **Planned:** editing/voiding a completed sale from the desk itself;
  barcode-scanner hardware integration (today it's a text field, not real
  scanner hardware).

## 5. Multi-Branch Inventory

- Stock table showing every active product across all branches, with
  computed In Stock / Low / Out badges.
- Filters: branch (multi-select pills), category, brand, stock status,
  free-text search; pagination.
- Inter-branch stock transfer (validates source stock, moves quantity,
  logs a `StockTransfer` record).
- **Planned:** transfer approval workflow (currently transfers apply
  immediately); low-stock email/notification alerts; purchase
  orders/receiving from suppliers.

## 6. Customer History

- Searchable customer list → profile page: total spend, last visit,
  favorite brand, and store credit — all computed from real sales data.
- Saved Color Formulas grid and Recent Purchases table.
- Quick Re-tint: reload a saved formula straight into the Tinting Desk to
  start a new sale with it.
- Editable customer notes.
- **Planned:** creating/editing customers from the UI (currently seeded/
  added via `/admin/` only); loyalty points beyond the existing store-credit
  field; SMS/email receipts.

## 7. Catalog & Admin

- Products, categories, brands, pigments, and color formulas are managed
  through Django admin (`/admin/`) today — no staff-facing "add product"
  screen yet.
- Each product has a `cost_price` alongside its `unit_price`. It's optional
  (defaults to 0) but drives every profit figure in Reports — a product
  with no cost on file shows "—" for margin instead of a false 100%.
- **Planned:** a staff-facing product/catalog management screen so
  managers don't need admin access for routine catalog edits.

## 8. Reports & Profit/Loss

- Manager-only `/reports/` page, filterable by date range and branch.
- **Profit & Loss:** net sales (after all discounts), cost of goods sold
  (from each sale line's cost snapshot — tinted cans include the base can
  plus the pigment that went into them), gross profit, gross margin %, and
  a breakdown of order-level vs. line-item discounts given.
- **Best-Selling Products:** revenue, units, and margin % per product for
  the selected period.
- **Losing Money:** products whose revenue this period, after discounts,
  was actually below what they cost — the discount-driven kind, not a
  simple low-margin item. Requires a cost price on file to appear.
- **Slow-Moving Stock:** active products with on-hand stock that haven't
  sold in `DEAD_STOCK_DAYS` days (default 30, in `chromapos/settings.py`),
  including items that have never sold at all, with the cash value tied
  up in each.
- Exports (CSV / XLSX / PDF) mirror everything on the page, including the
  P&L summary, best/worst sellers, and slow-moving stock.

## 9. Non-functional

- **Database:** SQLite for local dev; swappable to Postgres via
  `chromapos/settings.py` `DATABASES` without app-code changes.
- **Payments:** recorded in the database only — no real payment gateway
  integration (Stripe, Square, etc.) is wired up.
- **Search:** global top-bar search covers products and customers.
- **Tests:** smoke-test coverage for sales checkout flow, inventory
  transfers, and customer views (`python manage.py test`).
- **Out of scope (not planned):** multi-currency, tax-jurisdiction rules
  beyond a flat 8%, offline/PWA mode, hardware receipt printer integration
  beyond browser print.

## 10. Reference

- Design source: `stitch_paint_retail_pos_system/` (Stitch mockups +
  `chromatic_enterprise/DESIGN.md` design system).
- Seed/demo data: `python manage.py seed_demo_data` (see `README.md`).
