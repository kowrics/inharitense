# ECMCI v11 — Figma-integrated Capstone Build

**Purpose:** Stable, demonstrable academic capstone system.  
**UI baseline:** Shared ECMCI Figma file, sage/white palette, Inder headings, DM Sans body, rounded controls, light/dark theme, full-width workspace with slide-out navigation.

## Retained core modules

- Dashboard and category-aware inventory management.
- Stock movements and transaction history.
- Stock requests, review, approval, rejection, and fulfillment.
- Assignments and electronic acknowledgement.
- Physical inventory counts and manager-approved stock adjustments.
- Asset disposal requests and Finance approval.
- Asset circulation (transfer/return) and maintenance records.
- Purchase requisitions, approval, purchase orders, supplier selection, receiving, and receipt history.
- Demand forecasting, reports, detailed exports, and audit trail.

## QA improvements included

- Unique temporary passwords, one-time credential presentation, mandatory password change at first login, read-only registered email, show/hide controls, and 30-minute inactivity timeout.
- Numeric unread notification badge and account-specific notification read status. Panel open is non-destructive; opening an individual notification marks only that notification for the current account; Mark All as Read is explicit.
- Low-stock and out-of-stock alerts on stock transitions including stock issue, request fulfillment, assignment, approved disposal, approved stock adjustment, receiving/opening stock as appropriate. Duplicate entry conflicts produce role alerts.
- Per-account stock-request submission limit (five submissions in a rolling 60-second window).
- Success feedback, field-level invalid styling, profile Settings/Log Out menu, role-based navigation, and empty placeholders on required choice fields.
- Shared unsaved-change guards for dirty forms/modals, with Continue Editing and Discard Changes; successful saves can clear the dirty state. Browser-local drafts for selected forms; Physical Inventory and Maintenance drafts use database-backed workflows.
- Transfer confirmation and maintenance recorder identity/timestamps shown in history; Maintenance drafts are resumable and owner-scoped, and successful saves return to the Maintenance view.
- Inventory item images (JPEG/PNG/WebP, up to 2 MB).
- CSV/XLSX stock import with preview, validation, duplicate recheck, all-or-nothing save, and opening-stock movement history.
- Target-aware notifications; generated requisition, Client Reports overview, and Audit Trail movement PDFs; synthetic forecast history isolated in a labelled demo-only table; updated requisition/receiving status presentation; single Audit Trail Excel/PDF export menu.
- Expanded light/dark styles and collapsible navigation drawer while retaining the existing v11 visual system.

## Defense run mode

Use `run.bat` on Windows. The local launcher uses the bundled SQLite database, sets `APP_ENV=development`, binds to `127.0.0.1:5000`, creates a project-local `.venv`, and installs `requirements-capstone.txt`. It never deletes or recreates the existing database. Do not use Docker or PostgreSQL for the defense unless your actual demonstration environment specifically requires it.

## Known boundaries to explain honestly

- Form drafts (except Physical Inventory drafts) are local to the same browser/device and account.
- SMTP email is optional configuration; in-app alerts work independently.
- Duplicate checking is exact name/tag/code matching, not fuzzy matching.
- Asset circulation is quantity-level, not a serialized per-asset custody ledger.
- Purchasing functionality records internal requisitions, POs, supplier selection, and delivery receiving. External supplier negotiation and payments are outside system scope.
- Bulk import has 200-row/5 MB limits; images have a 2 MB limit.
- PostgreSQL remains an optional adapter; the recommended defense environment is local SQLite.

## Verification

See `QA_PROGRESS.md` and `FINAL_QA_REPORT.md`. The test suite currently collects 200 tests, including supplementary client QA cases. The latest full suite remains pending on the Windows defense machine because Flask/Werkzeug are unavailable in the preparation runtime. The verification environment used to prepare this package does not have Flask/Werkzeug, so full pytest execution must be performed in the project's `.venv` on the defense laptop. Do not describe the suite as passed until `python -m pytest -q` reports no failures on this package revision.
