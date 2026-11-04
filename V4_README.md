> For current setup and reliability changes, read README.md first.

# INHARITENSE v4 — ECMCI Recommendations Build

This build upgrades the v3 demo-ready system to the revised ECMCI inventory process.

## Revised roles
Existing demo accounts are migrated automatically:
- admin@ecmci.com / admin123 -> Super User
- encoder@ecmci.com / encoder123 -> Encoder
- reports@ecmci.com / report123 -> Report Generator
- employee@ecmci.com / employee123 -> Employee

## New modules
- Employee Item Assignment + electronic acknowledgement
- Purchase Requisition register/generator
- Inventory Reports (date acquired / department filters; weekly/monthly selector; CSV export)
- Physical Inventory Audit with expected-vs-actual variance
- ECMCI category + GL classification settings
- Revised four-role RBAC
- Revised category code/tagging support

## Run on Windows
1. Extract this ZIP.
2. Double-click `run.bat` (same workflow as v3).
3. Open the local URL shown by Flask.
4. Sign in using one of the demo accounts above.

The included SQLite database is a copy of the v3 database. On first run, v4 adds the new tables/columns and migrates the old demo roles/categories while preserving the records.

## Suggested test order
1. Login as Super User and check Inventory / Users.
2. Login as Encoder and assign an item to the Employee.
3. Login as Employee and acknowledge it by typing the employee name as e-signature.
4. Login as Report Generator and check Inventory Reports.
5. Login as Encoder and create a Purchase Requisition.
6. Login as Encoder and start an Inventory Audit, enter actual counts, then finalize it.

## ECMCI alignment update (September 2026)
- Four system roles: Super User, Encoder, Report Generator, Employee.
- ECMCI inventory categories/classification and category codes.
- New inventory tags generated as Category-Description-Year Acquired-Number Series.
- Receiving/disbursement remain Stock IN / Stock OUT transactions with movement history.
- Employee item assignment includes electronic acknowledgement.
- Inventory reports support acquisition-date and department filters plus weekly/monthly views.
- Stock Movement Excel/print output follows: Date, Item No., Item, Type, Quantity, Note, Recorded By.
- Purchase Requisition prepares a printable requisition-information report for ECMCI's separate requisition/purchasing system.
- Physical inventory audit records expected, actual, variance status, numeric variance, and discrepancy notes.
- Forecasting/vendor pages remain in the codebase as optional/legacy modules but are not primary navigation requirements.

Note: ECMCI's source process lists `PS` for both Pantry Supplies and Pantry Utensils. This build uses `PU` for Pantry Utensils to keep generated inventory tags unique until ECMCI confirms the official code.


## Modern UI / Theme update
- Added modern light/dark UI with one-click theme toggle.
- Theme preference persists in the browser.
- Redesigned dashboard, cards, tables, forms, login screen, and responsive layout.
- No inventory/database workflow logic was intentionally changed by this UI pass.

## AI/ML + EOL update

This build restores the paper-defined AI/ML scope:
- AI/ML Demand Forecasting for consumable inventory using dependency-free Linear Regression over up to 26 weeks of Stock OUT history.
- Dynamic reorder point recommendations using predicted demand, lead time, and safety stock.
- AI output is advisory only; it never places purchase orders automatically.
- Forecast data-quality status is shown. Fewer than 4 active usage weeks returns an insufficient-data result rather than a fabricated forecast.
- Asset Lifecycle / End-of-Life monitoring for equipment, furniture, utensils, and staff-house assets.
- Vendor Masterlist and QR/barcode scanning are restored to main navigation/workflow.
- Duplicate inventory item number/name/code protection and low-stock/in-app notification foundations remain enabled.

Forecast categories: Office Supplies, Janitorial Supplies, Pantry Supplies, Emergency Food.
Asset/EOL categories: equipment, furniture/fixtures, pantry utensils, and staff-house asset categories.
