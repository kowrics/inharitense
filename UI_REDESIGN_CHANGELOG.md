# ECMCI v10 — Actual Interface Redesign

This is an update to the real Flask/Jinja templates, **not a concept image**.

## Changed
- Rebuilt **Inventory Reports** with compact horizontal filters, live calculated summary cards, report export actions, text search, client-side pagination and a clear table hierarchy.
- Preserved existing server filter parameters, Excel/CSV endpoints, PDF/print link, role-based navigation, and dark/light theme.
- Reduced spacing and redundant headings across Procurement, Asset Controls, Asset Operations, and Detailed Exports.
- Added `static/js/report-ui.js` for local table search/pagination without changing stock or server records.

## Honesty about metrics
- Inventory records, on-hand units, unique categories and custody records come from already-filtered server data.
- Counts reflect the currently filtered data. On-hand units are current stock, not historical totals.

## Still requires verification
- Full browser functional testing on the user's Windows machine.
- Additional rework of older Inventory, Stock Requests, and Assignments screens.
- Procurement and role workflow completeness remains governed by the v10 preview limitations.

## Installation
Extract this ZIP as a new folder. Keep your original v9/v10 backup; run with `run.bat`.

## v11 Figma UI integration

- Applied the ECMCI Figma sage/white design palette, Inder headings, DM Sans body typography, rounded controls, white workspace panels, and pale-green table headers across the application shell.
- Replaced the persistent navy sidebar layout with a compact top action bar and an accessible slide-out navigation drawer so the Figma full-canvas page layout is preserved while all existing routes remain reachable.
- Split Asset Circulation and Maintenance into dedicated views while keeping the existing transfer, return, and maintenance POST endpoints.
- Reorganized Procurement & Receiving into the Figma four-stage workflow: Approvals, Create Order, Receiving, and Receipt History.
- Reorganized Stock Corrections and Disposal Requests into separate workspaces, with request dialogs reusing existing approval routes.
- Reworked Users into account creation, role information, and active-account views; added a dedicated read-only Audit Trail route.
- Aligned Account Settings with the two-card Figma layout and changed the first-visit theme default to White Mode. A previously saved theme preference is preserved.
- Added a root `.gitignore` for local databases, environment files, backups, virtual environments, and generated artifacts.

Existing inventory, procurement, approval, and reporting business operations were preserved; new UI controls submit to the existing routes.
