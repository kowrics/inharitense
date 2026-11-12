# ECMCI Capstone QA — Implementation and Verification Report

**Package:** ECMCI v11 Figma-integrated capstone build  
**Date:** 2026-11-13  
**Scope:** Phases 1–6 plus supplementary client findings A–K, focused acceptance tests, static checks, targeted Chromium form-guard checks, and isolated SQLite migration validation.  
**Important:** This report separates implementation from executed verification. It does not claim the current full pytest suite passed because Flask is not installed in the preparation environment.

## 1. Executive summary

The remaining QA implementation has been integrated into the existing v11 project with the Figma UI and core inventory/procurement/approval/reporting modules retained. The scope is optimized for a local academic defense: SQLite, optional SMTP, browser-local drafts for selected long forms, and a preview/confirm bulk-import flow. Docker, PostgreSQL staging, hosted deployment, queues, and CI/CD are not required for the recommended defense configuration.

The current project collects **200 automated tests**. Python/JavaScript/Jinja/CSS static checks, a targeted unsaved-change Chromium harness, and a non-destructive SQLite migration check passed. The full pytest suite could not execute in this preparation environment because Flask/Werkzeug are unavailable. The earlier user-local run (on a previous 172-test revision) reported 171 passed and one stale Reports UI assertion; that assertion was updated, but the current 207-test package still requires a full local run.

**Implementation status:** Phases 1–6 code and documentation are included.  
**QA certification status:** Not yet fully certified. Current full pytest and the defense-laptop browser walkthrough remain outstanding.

## 2. Implementation summary

### Phase 1 — Security and account management

- New accounts receive cryptographically random temporary passwords (20 characters, letters and digits).
- Only a one-time generated credential is displayed; a unique fingerprint is stored, not the plaintext temporary password.
- New accounts must change the temporary password before accessing protected application modules.
- Registered email is read-only in Account Settings and backend updates that attempt to change it are rejected.
- Login and Settings password fields have show/hide controls.
- Password confirmation is validated in the browser and backend; current password values are not repopulated by the server.
- Permanent sessions expire after 30 minutes of inactivity. Background API polling does not advance the inactivity marker; explicit activity keepalive does.

### Phase 2 — Notifications and request management

- Notification read status is stored per account in `notification_reads`.
- Opening the notification panel does not mark notifications read; opening an individual item marks only that item for that account; Mark All as Read remains explicit.
- Unread notification count appears as a numeric badge.
- Low-stock/out-of-stock alerts are generated on stock threshold transitions, including assignments, request fulfillment, stock movement, approved disposal/adjustments, and receiving/opening stock paths.
- In-app alerts are always available. SMTP email is optional and requires user-supplied mail settings.
- Exact inventory name/tag/code duplicates are blocked with HTTP 409 and role notifications.
- Stock-request submission is limited to five submissions per user within a rolling 60-second window; excess submissions receive HTTP 429.

### Phase 3 — UI and form improvements

- Shared success messages have stronger contrast/visual emphasis.
- Native required-field validation marks invalid controls with a red border and clears the state when corrected.
- Profile dropdown contains Settings and Log Out.
- Role-based sidebar visibility is retained and checked against an eight-role expected navigation matrix.
- Required data-entry selectors use empty/Choose placeholders; deliberate report/filter defaults are retained.

### Phase 4 — Additional workflow features

- Selected longer forms have account-specific browser-local Save Draft / Clear Draft controls. Passwords, CSRF fields, hidden fields, and file inputs are excluded. Existing database-backed Physical Inventory drafts remain unchanged.
- Transfer history displays requester and confirming user/timestamp. Maintenance history displays recorder and record timestamp.
- Inventory image upload supports JPEG/PNG/WebP, signature validation, generated filenames, and a 2 MB cap.
- Bulk inventory import supports CSV/XLSX, preview, validation, exact duplicate checking, 200 rows / 5 MB limits, a single all-or-nothing confirmation, and opening-stock movement records.

### Phase 5 — Documentation and scope alignment

- Documentation now describes internal requisition approval, purchase-order recording, supplier selection, and delivery receiving as system workflows.
- External supplier negotiation, payment processing, and external accounting transactions are explicitly distinguished as out of scope.
- Added a capstone run guide and panel demonstration walkthrough.

### Phase 6 — Automated/practical QA preparation

- Added focused acceptance tests for notification isolation, low-stock transitions, SMTP transport (fake transport), spam prevention, duplicate alerts, image upload, CSV/XLSX import, transfer/maintenance recorder visibility, procurement-to-receiving behavior, and role navigation.
- The suite currently collects 207 tests, including supplementary client-QA coverage and the new inventory delete-flow regression cases.
- A practical demonstration sequence is documented in `DEFENSE_DEMO_GUIDE.md`.

## 3. Files modified or added in this capstone pass

### Runtime/setup

- `requirements-capstone.txt` — minimal dependencies for local SQLite demonstration (Flask, Werkzeug, openpyxl, ReportLab).
- `requirements-dev.txt` — capstone dependencies plus pytest.
- `run.bat` — local SQLite launcher using a project-local `.venv`; it does not reset the database.

### Documentation

- `README.md` — local capstone setup, demo accounts, feature scope, SMTP option, DB safety, troubleshooting.
- `CLIENT_REQUIREMENTS_PROGRESS.md` — aligned with current implemented features and capstone boundaries.
- `V11_IMPLEMENTATION_NOTES.md` — v11 and QA implementation summary/known limits.
- `QA_PROGRESS.md` — 22-item QA matrix and evidence.
- `DEFENSE_DEMO_GUIDE.md` — panel walkthrough, preparation, and recovery notes.
- `FINAL_QA_REPORT.md` — this report.

### Exact file changes compared with `ECMCI_v11_Phase1_PostTestFix.zip`

**Modified:** `.gitignore`, `CLIENT_REQUIREMENTS_PROGRESS.md`, `QA_PROGRESS.md`, `README.md`, `V11_IMPLEMENTATION_NOTES.md`, `app.py`, `requirements-dev.txt`, `run.bat`, `static/css/app.css`, `static/css/figma-ui.css`, `static/js/app.js`, `templates/asset_controls.html`, `templates/asset_operations.html`, `templates/assignments.html`, `templates/base.html`, `templates/inventory.html`, `templates/procurement.html`, `templates/requests.html`, `templates/requisitions.html`, `templates/settings.html`, `templates/users.html`, `templates/vendors.html`, `tests/test_phase1_security.py`, and `tests/test_v7.py`.

**Added:** `DEFENSE_DEMO_GUIDE.md`, `FINAL_QA_REPORT.md`, `requirements-capstone.txt`, `static/js/drafts-ui.js`, `templates/inventory_import_preview.html`, and `tests/test_capstone_qa.py`.

### Exact delta for the supplementary client-QA round (compared with the prepared pre-round source copy)

**Modified:** `CLIENT_REQUIREMENTS_PROGRESS.md`, `DEFENSE_DEMO_GUIDE.md`, `FINAL_QA_REPORT.md`, `QA_PROGRESS.md`, `README.md`, `V11_IMPLEMENTATION_NOTES.md`, `app.py`, `static/css/figma-ui.css`, `static/js/drafts-ui.js`, `static/js/unsaved-changes.js`, `templates/audit_trail.html`, `templates/procurement.html`, `templates/reports_v4.html`, `templates/requisitions.html`, and `tests/test_capstone_qa.py`.

**Added:** `tests/test_additional_qa.py`.

No source files were removed in this supplementary round. The bundled SQLite file was not modified.

No existing report, dashboard, inventory, procurement, forecast, approval, or Figma layout was intentionally redesigned. Styling changes are limited to the requested success/validation treatments and capstone interactions.

### Application/features already included in the prepared source tree

- `app.py` — account controls, inactivity enforcement, notifications, request throttle, image handling, import handling, and existing business workflows.
- `static/js/security-ui.js`, `static/js/drafts-ui.js`, `static/js/app.js`, and current CSS/templates — security controls, notification/profile interactions, drafts, and Figma-integrated UI.
- `migrations/v8_phase1_security.sql` — optional PostgreSQL reference migration.
- `tests/test_phase1_security.py`, `tests/test_capstone_qa.py`, and the existing test suite — focused acceptance and regression cases.

The Figma-integrated visual styles/templates were not redesigned in this capstone pass. The local app continues to use the sage-green/white interface.

## 4. Executed checks and results

| Check | Result | Notes |
|---|---|---|
| Python compilation | **Passed** | `python -m py_compile app.py tests/*.py` |
| Pytest collection | **Passed** | 207 tests collected in the latest collection run |
| JavaScript syntax | **Passed** | `node --check` on every `static/js/*.js` |
| Jinja syntax | **Passed** | 24 templates parsed; zero errors |
| CSS parsing | **Passed** | Three stylesheets parsed; zero parser errors |
| SQLite migration check | **Passed on isolated copy** | Actual `init_db()` executed twice against a backup copy; no foreign-key violations; `quick_check=ok` |
| Original SQLite file | **Preserved** | Migration script used an independent backup file; original `inharitense.db` was not opened as a migration target |
| Current full pytest execution | **Blocked by environment** | Flask/Werkzeug are missing in this preparation environment; test bodies could not start. This is not a reported 207-test product failure. |
| Live browser/application smoke test | **Pending** | Must be performed on the defense laptop with Flask installed |
| Live SMTP delivery | **Optional / not tested** | Fake SMTP transport test exists; actual delivery needs demo mailbox settings |
| PostgreSQL runtime | **Not required for capstone** | Local defense configuration uses SQLite; PostgreSQL remains optional |

### SQLite migration detail

The migration verification copied `inharitense.db` using SQLite's backup API, created a test legacy role notification in the copy, then imported the application's real `init_db()` function and executed it twice. A minimal Flask import shim was used only because the environment lacks Flask; database access and migration SQL were performed by the application's actual SQLite connection/schema functions.

Results:

- SQLite quick check: `ok`.
- Foreign-key violations: `0`.
- Existing user IDs and password hashes: preserved.
- Existing inventory IDs, tags, names, quantities, and costs: preserved.
- Existing movement rows and vendor rows: unchanged.
- Legacy shared read flag: normalized to `0`; per-account read markers created for the current active role recipients.
- Repeated migration: completed without error.

This is not a live Flask request test, and it does not imply PostgreSQL execution was tested.

## 5. Test-suite issue history

The user previously supplied a Windows run on an earlier package revision:

```text
172 tests collected
171 passed, 1 failed
```

The sole failure was `test_weekly_reports_keep_older_stock_and_legacy_department`, whose assertion expected the old phrase `Reset filters`. The current approved Figma-integrated Reports page uses `Clear all`; the link already reset to `/reports-v4`. The application UI was deliberately preserved and the stale test expectation was corrected.

The current suite has grown to 207 tests through additional phase and supplementary client-QA acceptance coverage. The current package has not yet been fully executed on the user's Windows environment, so it is not accurate to claim 200 passed.

## 6. Supplementary implementation — additional client QA findings (2026-11-13)

### Forms, account setup, Settings

- Shared unsaved-changes confirmation covers dirty modal close/backdrop/Escape, form reset, navigation attempts, and browser unload. Continue Editing preserves values; Discard Changes resets the modal form before closing. Dynamic forms are observed. AJAX workflows can dispatch a saved event to suppress false warnings after success.
- The Phase 1 one-time temporary password and first-login password-change flow remains in place. The generated password is displayed only in the account creation response and is not stored in notifications.
- Settings presentation and dark-mode treatment have been refined within the retained application UI and existing profile/password features remain present.

### Notifications and workflows

- Notifications carry internal target URLs for request, requisition, receiving, transfers, maintenance, adjustment/disposal, and low-stock workflows. Individual reads remain per-user; opening the panel does not implicitly mark all as read.
- Added/extended event notifications for key submissions, decisions, and status changes. This was source-reviewed, but there is not yet one executed route test for every event type.
- Maintenance save returns to Maintenance. Server-side maintenance drafts are owner-scoped, persistent, resumable, and separately deletable from submitted maintenance records.
- Physical Inventory finalization rejects an empty audit and incomplete count/discrepancy data server-side. Row-level errors are available to the form for highlighting.

### Procurement, forecast, reports, exports

- Requisition and report overview PDF endpoints generate ReportLab documents and return attachment downloads. Overview content includes current counts/statistics and a generation timestamp.
- Receiving/order views display item names with item codes as supporting identifiers. Approved requisitions remain visible in the order/receiving area after PO creation with updated status and PO linkage.
- Synthetic historical forecast rows are seeded into the separate `forecast_demo_movements` table and clearly marked `[DEMO SAMPLE]`; they do not add/subtract actual inventory quantities or contaminate the actual `movements` ledger.
- Audit Trail has a single Export Movements menu for Excel and PDF. The duplicate Jinja `scripts` block was removed.
- Draft/submit/receive action groups and dark-mode component states were adjusted using existing stylesheet conventions; sidebar navigation now has a slide-out/backdrop behavior and compact category labels.

### Additional test files and code touched in this round

- Added `tests/test_additional_qa.py` for physical audit completeness, maintenance draft ownership/persistence, maintenance redirect, PDF attachment responses, forecast history isolation, notification targets, and shared form-guard behavior.
- Extended procurement-to-receiving regression assertions for the requisition/order relationship and visible product name.
- Modified `app.py`, `static/js/unsaved-changes.js`, `static/js/drafts-ui.js`, `static/css/figma-ui.css`, and templates for Audit Trail, Reports, Procurement, and Requisitions. Exact added/modified files in the source tree are described in the delivered package's QA matrix; the older “compared with Phase1 ZIP” list above describes only the earlier phase and is not a complete diff for this supplementary pass.

### Important design-reference boundary

The working source contains the previously integrated v11 design language and the UI edits were applied consistently within those styles. The original Figma file URL/node could not be recovered from the current conversation attachments or project tree, so this pass cannot claim a fresh frame-by-frame Figma canvas inspection. No wholesale redesign was performed.

## 7. Additional executed checks and limitations

| Check | Latest result | Qualification |
|---|---|---|
| `python -m py_compile app.py tests/*.py` | **Passed** | Python syntax only. |
| `node --check` on all `static/js/*.js` | **Passed** | All current JavaScript files. |
| Jinja compilation | **Passed** | All 24 templates compile after Audit Trail block correction; standalone validation registered the app's custom `dt` filter. |
| CSS parsing | **Passed** | `app.css`, `figma-ui.css`, `workspace-redesign.css`; no parser errors. |
| Pytest collection | **Passed** | 207 tests collected. |
| Focused pytest form-guard assertion | **Passed** | 1 test passed for dynamic-form/reset-guard source behavior. |
| Targeted Chromium harness | **Passed** | Continue, discard/reset, and successful AJAX-save clean-state cases passed using a controlled HTML fixture; not a full Flask application browser session. |
| Latest complete pytest run | **Not executed** | Flask and Werkzeug are missing in this environment; install `requirements-dev.txt` and run on the Windows defense machine. |
| Full-app visual/responsive acceptance | **Pending** | Test both themes and desktop/mobile drawer behavior in the target browser. |

## 8. Remaining verification before declaring defense-ready

1. On the defense laptop, install `requirements-dev.txt` in the project-local `.venv` and run `python -m pytest -q`. The expected collection count is 207. Record the full result.
2. Run `run.bat` and complete the walkthrough in `DEFENSE_DEMO_GUIDE.md`.
3. Specifically smoke-test draft save/restore/clear in the browser; the existing suite checks form annotations but not every browser localStorage interaction.
4. Test first-login password change, account-specific notifications, and inactivity expiry in the actual running app.
5. Test inventory image display and one CSV plus one XLSX import/confirm cycle using demo records.
6. Demonstrate the stock request/approval/fulfillment and purchase requisition/approval/PO/partial receiving workflows.
7. If actual outbound email is required during defense, set SMTP variables and send a controlled test to the demo mailbox. Otherwise explain that in-app notifications work independently and email is optional transport.



## 9. Final disposition

**Implementation:** Phases 1–6 code and documentation are included in the updated package.  
**Automated QA:** 207 tests collected; one focused pytest assertion passed, while the latest full run remains pending because Flask/Werkzeug are unavailable in the preparation environment.  
**Database:** Additive SQLite migration check passed on a copy; original DB was not modified.  
**UI:** Figma-integrated design preserved.  
**Supplementary client findings:** Implemented in source with focused coverage added for form guards, audit completeness, maintenance drafts/routing, PDFs, forecast demo-data isolation, and notification targets. These new route tests have been collected but not executed against a live Flask app in this environment.

The project is prepared for the final local regression run and defense-laptop walkthrough, but should not be described as fully QA-certified until those final runtime checks pass.

### Targeted follow-up fix — Inventory modal close buttons (2026-11-13)

- The Add Inventory Item and Stock Movement modal X controls now use the shared `data-ui-modal-close` handler instead of closing inline before the asynchronous unsaved-changes prompt can resolve. The Add Item Cancel control uses the same managed close path.
- The shared handler now owns clean closes as well as dirty-form confirmation for these explicitly managed controls. `Continue Editing` leaves the modal and entered values intact; `Discard Changes` resets the form and closes it.
- `openItemModal` / `closeItemModal` also synchronize `aria-hidden` with the visible state.
- Verification performed: `node --check` for `app.js` and `unsaved-changes.js`, Python compilation, and Jinja parsing of all 24 templates passed. A headless Chromium interaction attempt timed out in this environment; the live browser interaction remains to be confirmed on the defense laptop.

### Targeted navigation enhancement — Back button and left drawer control (2026-11-13)

- Added global Back and sidebar toggle controls to the shared page header. Back is separate from the drawer toggle: Back changes to the previous in-app page, while the drawer toggle only opens/closes navigation.
- Previous page locations are kept in account-scoped session storage for the current tab. Direct page entry falls back to Dashboard; browser history is reconciled when a previously visited page is revisited.
- Controls are positioned to the left of the page title and styled with the existing theme variables for light/dark consistency and responsive layouts.
- Added source-level regression coverage. JavaScript syntax, template parsing, and visual/browser behavior must still be checked in the actual defense browser; no live-browser pass is claimed here.

### Targeted follow-up fix — Inventory item deletion (2026-11-13)

- Expanded the delete endpoint's relationship checks to cover asset disposals, stock adjustments, asset transfers/returns, and maintenance history in addition to movements, requests, assignments, audits, and purchase requisitions. This prevents unhandled foreign-key failures and preserves operational history.
- Newly created or imported items can be permanently deleted when their only movement rows are the one-time `Opening stock` / `Bulk import opening stock` entries. Those setup-only rows are removed in the same database transaction. Any later stock movement still blocks deletion.
- Synthetic forecast demo rows are removed with the item; they are separate from real stock history.
- Delete controls now appear for both Super User and Admin, matching the backend permission policy. The browser handler now handles JSON and non-JSON server responses and surfaces useful error messages.
- Added regression coverage for deleting unused items, deleting items with only opening stock, and protecting items linked to disposal, adjustment, transfer, or maintenance records. Existing transaction-history protection remains in place.
- Verification performed: Python compilation, JavaScript syntax validation, and Jinja parsing of all 24 templates passed; pytest collection reports 207 tests. The full test suite could not execute in this preparation environment because Flask is not installed (`ModuleNotFoundError: No module named 'flask'`). Live browser verification remains to be completed on the Windows defense machine.
