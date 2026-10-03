# ChromaPOS

A Django-based point-of-sale system for a paint retail chain, built from the
`stitch_paint_retail_pos_system` design set (Sales & Tinting Desk,
Multi-Branch Inventory, Customer History).

## Stack

- Backend: Django 6.1, Python 3.14, SQLite (dev)
- Frontend: server-rendered Django templates, Tailwind CDN, vanilla JS (fetch-based AJAX for the cart/tinting desk)

## Setup

```powershell
cd "paint pos"
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py seed_demo_data   # idempotent — safe to re-run
venv\Scripts\python.exe manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

## Accounts

All staff passwords are `chromapos123` except the Django admin superuser. Every branch has its own
manager + cashier login, named `manager_<branch-code>` / `cashier_<branch-code>`.

| Branch           | Manager       | Cashier       |
|------------------|---------------|---------------|
| Downtown Branch  | manager1      | cashier1      |
| North Hub        | manager_nhb   | cashier_nhb   |
| Industrial Park  | manager_ind   | cashier_ind   |
| Westside         | manager_wst   | cashier_wst   |
| East Depot       | manager_est   | cashier_est   |

| Purpose      | Username | Password     |
|--------------|----------|--------------|
| Django admin | admin    | admin12345   |

Django admin is at `/admin/`. Staff POS login is at `/accounts/login/`.

## Apps

- `accounts` — staff login, `Profile` (user ↔ branch ↔ role)
- `core` — `Branch`, shared base template/layout, global search
- `catalog` — `Category`, `Brand`, `Product`, `Pigment`, `ColorFormula` (+ tinting heuristic in `catalog/tinting.py`)
- `inventory` — `StockLevel`, `StockTransfer`, the Multi-Branch Inventory screen
- `sales` — `Sale`, `SaleItem`, `Payment`, the Sales & Tinting Desk screen, checkout, receipts
- `customers` — `Customer`, `SavedFormula`, the Customer History screen

## Notes on functional simplifications

- **Tinting formula**: there's no real spectrophotometer, so pigment mixes are computed with a heuristic (non-negative least squares against a small fixed pigment set) in `catalog/tinting.py`. It's editable/functional, not scientifically certified.
- **Payments**: cash/card are recorded in the database (with change due for cash); there's no external payment gateway. Partial payments are supported — paying less than the balance leaves the sale open for a second payment (basic split-payment support).
- **Branch-scoped operation**: a user must have a `Branch` assigned on their `Profile` (via `/admin/`) before they can use the Sales desk.

## Tests

```powershell
venv\Scripts\python.exe manage.py test
```
