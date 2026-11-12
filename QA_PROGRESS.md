# ECMCI Capstone QA Progress Matrix

**Project purpose:** Academic capstone defense and controlled live demonstration.  
**Implementation baseline:** v11 Figma-integrated project + Phase 1 security + capstone QA features.  
**Last updated:** 2026-11-13  
**Current focus:** Phases 1–6 plus the supplementary client QA findings A–K; full latest-revision regression run pending in the defense laptop environment.

## Status policy

- **Verified:** The relevant test or actual runtime check was executed successfully on the current package revision.
- **Partially verified:** Some targeted checks or prior-revision tests passed, but at least one current-revision runtime/acceptance check remains.
- **Implemented — test pending:** Code and a focused automated test exist, but the latest full test run has not executed.
- **Pending:** Work is not yet implemented.
- **Failed:** An actual test ran on the current revision and exposed an unresolved product defect.

Do not change a status to Verified just because the code or a test exists. The most recent supplied local full run was on the earlier 172-test package: 171 passed and one pre-existing report-page wording assertion failed. That test was corrected in `tests/test_v7.py`; the corrected latest 207-test suite has not yet been run locally.

## Requirement count reconciliation

The source QA document has **22 numbered requirements**:

- A.1–A.5: 5 security/account requirements.
- B.6–B.12: 7 interface/UX requirements.
- C.13–C.17: 5 notification/request requirements.
- D.18–D.21: 4 additional features.
- E.22: 1 scope/documentation requirement.

Section F repeats the bulk-import requirement in D.21 and adds no new numbered requirement. Track it once. The correct total is **22**, not 21 or 23.

## Requirement matrix

| QA # | Requirement | Phase | Implementation state | Verification state / evidence |
|---:|---|---:|---|---|
| 1 | Unique, random temporary passwords | 1 | Implemented: 20-character secrets-generated password; SHA-256 fingerprint and unique partial index; one-time display | **Partially verified.** Prior user-local 172-test run passed the Phase 1 tests. Current test `test_new_accounts_get_unique_random_temporary_passwords_and_force_change` is in the 207-test suite; latest revision run pending. |
| 2 | Show/hide password | 1 | Implemented on login and Settings password inputs | **Partially verified.** Earlier Chromium check passed; current `test_password_show_hide_controls_exist_on_login_and_settings` is collected, latest full run pending. |
| 3 | Registered email cannot be changed in Settings | 1 | Read-only form field plus backend rejection of altered email | **Partially verified.** Prior targeted check passed; current `test_registered_email_is_read_only_and_server_rejects_changes` is collected, latest run pending. |
| 4 | Logout after 30 minutes of inactivity | 1 | Server-side inactivity marker; only explicit keepalive updates it; background polling excluded; 2-minute warning | **Partially verified.** Prior targeted browser/function checks passed; current timeout tests are collected, live 30-minute end-to-end wait in the actual defense browser remains pending. |
| 5 | Password mismatch message without unnecessary field clearing | 1 | Client-side mismatch validation plus server-side confirmation; no password value is repopulated from server | **Partially verified.** Prior targeted browser/function checks passed; current mismatch test is collected, latest run pending. |
| 6 | More visible request-submission success notification | 3 | Existing success feedback retained and more visible via shared `.flash.success` styling | **Implemented — test pending.** Style is present and checked by `test_phase2_6_ui_accessibility_and_placeholders_are_present`; latest full suite pending. |
| 7 | Highlight invalid/empty required fields | 3 | Native constraint validation adds `.field-invalid`; style is visible and clears when a field becomes valid | **Implemented — test pending.** Static/UI assertion exists; actual browser form-by-form smoke pass remains pending. |
| 8 | Profile dropdown with Settings and Log Out | 3 | Existing profile area opens a small Settings/Log Out dropdown; keyboard Escape/outside click close it | **Implemented — test pending.** Template/JS assertions exist; latest suite pending. |
| 9 | Numerical unread-notification badge | 2 | API returns per-user unread count; UI displays count, capped visually at 99+ | **Implemented — test pending.** Notification API/read test is collected; latest suite pending. |
| 10 | Unread highlight disappears after individual read | 2 | Individual Mark as Read/open action marks only that item for the current user and reloads the list | **Implemented — test pending.** Per-account notification workflow test covers the state change; latest suite pending. |
| 11 | Hide unauthorized sidebar modules/labels | 3 | Role-gated navigation retained and aligned with backend endpoint policy | **Implemented — test pending.** `test_role_navigation_hides_modules_outside_role_policy` checks the eight role labels; latest suite pending. |
| 12 | Dropdowns begin with a placeholder | 3 | Required data-entry selectors use empty/Choose placeholders; intentional filter/default selectors retain a sensible default | **Implemented — test pending.** Template assertions exist; an exhaustive manual visual pass is still useful. |
| 13 | Prevent rapid repeated stock requests | 2 | Per-account DB event window; five stock-request submissions per 60 seconds; sixth receives HTTP 429 and `Retry-After` | **Implemented — test pending.** `test_request_submission_rate_limit_returns_429_and_does_not_create_sixth_request` is collected; latest suite pending. |
| 14 | Notification read status is per account | 2 | Additive `notification_reads(notification_id,user_id,read_at)` table; old shared read flags are backfilled for current recipients, then normalized | **Implemented — migration check passed on isolated SQLite copy; latest route test pending.** `test_legacy_shared_notification_reads_are_backfilled_per_current_account` and account-isolation route test are collected. |
| 15 | Consistent notification read policy | 2 | Agreed policy implemented: panel open does not mark all; individual read marks one; Mark All remains explicit | **Implemented — test pending.** `test_notification_read_status_is_per_account_and_panel_get_does_not_mark` covers these semantics; latest suite pending. |
| 16 | Low-stock email and in-app notifications | 2 | Transition-based alert when quantity crosses minimum; zero-stock alerts; in-app always; SMTP optional | **Partially verified.** Unit/route tests cover threshold crossing, zero threshold, assignment, and a fake SMTP transport. Actual email delivery requires the defense mailbox's SMTP settings and is not claimed as live-tested. |
| 17 | Duplicate detection and alerts | 2 | Exact case-insensitive item name/tag/code check; duplicate attempts return HTTP 409 and notify Admin, Super User, Inventory Manager | **Implemented — test pending.** Inventory-save duplicate route test covers the conflict and role alerts; latest suite pending. No fuzzy similarity matching is claimed. |
| 18 | Save incomplete forms as drafts | 4 | Browser-local, per-account drafts on longer workflows; passwords, CSRF values, hidden fields, and file inputs excluded; Physical Inventory keeps database-backed drafts | **Partially verified.** Forms are annotated and JS is syntax-checked. A real browser save/restore/clear smoke test on the defense laptop remains pending. Drafts are same-browser/device only. |
| 19 | Transfer and maintenance confirmation/recorder details | 4 | Transfer history shows requested/confirmed by and timestamps; maintenance history shows recorder/date | **Implemented — test pending.** `test_transfer_confirmation_and_maintenance_recorder_are_visible` exercises the route and rendered names; latest suite pending. |
| 20 | Upload inventory item image | 4 | JPEG/PNG/WebP; signature validation; random stored filename; 2 MB limit; existing image preserved when no replacement supplied | **Implemented — test pending.** `test_inventory_image_upload_and_update_preserves_existing_image` is collected; latest suite pending. |
| 21 | Bulk stock import | 4 | CSV/XLSX, 5 MB, 200 rows, preview, validation, duplicate recheck, all-or-nothing commit, opening movement record | **Implemented — tests pending latest run.** CSV preview/confirm, fractional quantity rejection, XLSX Excel-date handling, owner binding, and single-use preview tests are collected. |
| 22 | Align procurement/purchasing scope documentation | 5 | Docs now distinguish internal requisition/PO/supplier/receiving records from external negotiations/payments | **Documentation updated.** Final confirmation that this phrasing matches the approved capstone paper is a team/panel matter, not a code test. |

## Supplementary client QA matrix (request dated 2026-11-13)

The additional findings in `Pasted text(1).txt` are tracked separately from the original 22-item QA checklist above. Status wording continues to distinguish source implementation from executed runtime verification.

| Ref. | Additional request | Implementation state | Verification state / evidence |
|---|---|---|---|
| A.1 | Warn before discarding unsaved form/modal values, including outside click, close, reset, and navigation | Implemented in shared `unsaved-changes.js` and shared confirmation dialog; dynamic forms are observed; successful AJAX saves can mark forms clean | **Partially verified.** Targeted Chromium harness exercised modal close/continue/discard, reset/discard, and successful-save clean state. Full in-app navigation/back-button acceptance on the defense browser remains pending. |
| A.1a | Inventory / Stock Movement modal X and Add Item Cancel close behavior | Fixed: close controls route through the shared unsaved-change guard; continue preserves edits, discard resets and closes | **Static/syntax checks passed.** `node --check` passed; browser interaction timed out in this environment and requires defense-laptop confirmation. |
| A.2 | Temporary password one-time display and forced first-login change | Implemented in Phase 1 account creation/login flow; plaintext is returned only once in no-store creation response and is not saved in notifications | **Partially verified.** Existing Phase 1 tests/previous targeted checks cover the flow; latest full suite remains pending. |
| A.3 | Settings visual organization and theme treatment | Updated retained Settings cards/sections and dark-theme styling without removing account/password functionality | **Implemented — visual acceptance pending.** Templates/CSS compile; no complete live-page screenshot review was possible in this environment. |
| B.4 | Notification click routes to relevant record and marks only that user's item read | Implemented `target_url` notification field, same-account read state, and target-aware UI navigation | **Implemented — route tests pending execution.** `test_notification_payload_has_workflow_target_and_nonrecipient_cannot_mark_read` is collected; role/recipient checks remain part of Flask runtime verification. |
| B.5 | Notify responsible users on request submission, decisions, and important status changes | Added notification calls for request submit/endorse/approve/reject/fulfill, requisition submission/decision/PO/receiving, transfer submit/confirm, maintenance, adjustment/disposal decisions, and low-stock transitions | **Implemented — broader event regression pending.** Static inspection confirms event hooks; not every event has its own distinct route assertion. |
| C.6 | Block Physical Inventory finalize until required audit entries and discrepancy notes are complete | Server-side field validation highlights row-level issues; finalization with no counted rows is rejected | **Implemented — test pending execution.** `test_physical_audit_requires_complete_rows_and_discrepancy_notes_before_finalize` and `test_empty_physical_audit_cannot_finalize` are collected. |
| C.7 | Save audit draft, confirm saved state, exit or continue, and resume saved draft | Existing database-backed Physical Inventory draft workflow retained with confirmation actions | **Partially verified.** Backend draft workflow existed; latest complete browser interaction (including Exit/Continue state) remains pending. |
| D.8 | Maintenance save remains in Maintenance workflow | Save handler redirects to `/asset-operations?view=maintenance` | **Implemented — test pending execution.** `test_maintenance_save_redirects_to_maintenance_view` is collected. |
| D.9 | Persistent Maintenance drafts, visible list, resume, and owner-only confirmed clear | Added `maintenance_drafts` table and owner-scoped save/load/delete endpoints; submitted maintenance records are separate | **Implemented — test pending execution.** `test_maintenance_drafts_persist_are_account_scoped_and_owner_deletable` is collected. |
| E.10 / F.15 | Balanced draft/clear/submit action groups across requisition and receiving screens | Added shared `.figma-form-actions` wrappers and sizing/alignment styles | **Implemented — visual acceptance pending.** Template/CSS parse checks pass; live responsive review remains pending. |
| E.11 | Purchase Requisition generates an actual downloadable PDF | ReportLab PDF route returns an attachment with requisition information | **Implemented — test pending execution.** Attachment disposition/content test is included in `tests/test_additional_qa.py`. |
| F.12 | Show item names with item codes as secondary context in Receiving | Receiving description displays inventory item name, with code shown secondarily | **Implemented — route/rendering test pending full run.** Procurement workflow test has been extended to assert item name visibility in the order register. |
| F.13 | Display approved requisitions as separate selectable cards | Updated separate selection/card styling and selected/unselected states in retained Procurement layout | **Implemented — visual acceptance pending.** CSS/template static review only; full visual browser pass remains pending. |
| F.14 | Keep approved requisitions visible after PO creation with up-to-date status and PO relationship | Requisition stage list retains ordered/partially received/received records and associated PO references in the order/receiving register | **Implemented — test pending execution.** Procurement regression now asserts PR persistence, PO reference, item name, and `Ordered` status. |
| G.16 | Provide safe demonstration forecast history | Synthetic weekly movement samples are stored only in `forecast_demo_movements`, labelled `[DEMO SAMPLE]`, and served through demo forecast flow; no rows are added to actual `movements` or stock balances | **Implemented — isolated-data test pending execution.** `test_forecast_demo_history_is_synthetic_and_separate_from_live_movements` is collected. |
| H.17 | PDF/print actions download generated reports rather than browser-page printouts | Relevant report, requisition, overview, and audit movement PDF endpoints use generated report data and attachment responses; Excel remains available | **Implemented — attachment tests pending execution.** Route tests assert PDF MIME/disposition; not every report variant has been manually downloaded in a browser. |
| H.18 | Client Reports overview PDF contains real record counts/statistics/date | Added ReportLab overview with live summary counts, category/stock and workflow figures, and generation timestamp | **Implemented — test pending execution.** Covered by overview attachment/report content test. |
| I.19–20 | One Audit Trail Export Movements menu with Excel and PDF | Added compact dropdown options for XLSX and generated PDF; duplicate Jinja `scripts` block removed | **Implemented — static validation passed, download tests pending.** `templates/audit_trail.html` has one scripts block; Jinja compile passes. |
| J.21 | Compact category label typography in sidebar | Reduced category label size/spacing in shared Figma UI stylesheet | **Implemented — visual acceptance pending.** CSS syntax parsed successfully. |
| J.22 | Collapsible left-side navigation drawer with backdrop, Escape/outside close, responsive behavior | Added toggle, fixed slide-in panel, backdrop, body interaction, and Escape/backdrop closing; role-based nav visibility retained | **Partially verified.** JS/CSS syntax and source checks pass; live responsive viewport/layout and role-by-role browser flow remain pending. |
| K.23 | Consistent light/dark interactive styling | Expanded theme token/overrides for buttons, fields, tables, dialogs, notifications, profile/settings, status and flash states | **Partially verified.** CSS parses without errors; contrast/readability and layout need visual inspection in the defense browser in both themes. |

### Latest supplementary checks (2026-11-13)

- `python -m py_compile app.py tests/*.py`: passed.
- `node --check` across all `static/js/*.js`: passed.
- Jinja compilation: 24 templates, 0 errors (including Audit Trail after duplicate script-block cleanup).
- CSS parser check: `app.css`, `figma-ui.css`, and `workspace-redesign.css`: 0 parser errors.
- `python -m pytest --collect-only -q`: **207 tests collected**.
- `python -m pytest -q tests/test_additional_qa.py::test_unsaved_change_guard_covers_dynamic_forms_and_reset_confirmation`: **1 passed**.
- Targeted Chromium harness: modal Continue Editing, Discard Changes, reset confirmation/discard, and successful AJAX save/clean state behaved as expected. This was a controlled fixture, not a complete Flask-rendered app session.
- Full pytest suite: **not executed** in this environment because Flask and Werkzeug are not installed. This is a dependency/runtime blocker, not evidence that the 200 application tests failed.
- The isolated SQLite migration verification from the prior phase remains valid; the original bundled DB was not used as a migration target. No additional DB migration was run against the bundled DB in this pass.

## Test inventory and current evidence

### Current package test collection

Command executed in this preparation environment:

```text
python -m pytest --collect-only -q
207 tests collected (latest collection; see executed evidence below)
```

The current suite comprises existing authentication, CSRF, roles, inventory, stock movements, requests, assignments, physical audit, forecasting, reports, and regression tests, plus Phase 1 security, capstone QA, and supplementary client QA acceptance tests in `tests/test_additional_qa.py`.

### Latest user-provided full run (previous 172-test revision)

```text
171 passed, 1 failed in 38.67s
```

The only reported failure was `tests/test_v7.py::test_weekly_reports_keep_older_stock_and_legacy_department`: the test expected the words `Reset filters`, while the Figma-integrated report page has an existing `Clear all` link. The template and behavior were already present in the earlier baseline. The test expectation was updated to match the existing UI and check its `/reports-v4` destination plus the accessible filter-removal label. This correction has not yet been confirmed by a user-local rerun.

### Checks performed during this preparation pass

- `python -m py_compile app.py tests/*.py`: passed.
- `python -m pytest --collect-only -q`: **207 tests collected** (latest run).
- `node --check` on every `static/js/*.js`: passed.
- Jinja parse: **24 templates, 0 parse errors**.
- CSS parse: `app.css`, `figma-ui.css`, and `workspace-redesign.css`: 0 parser errors.
- `python -m pytest -q --tb=short`: could not execute test bodies; the suite could not execute because importing the test fixture/application raised `ModuleNotFoundError: No module named 'flask'`. This is an environment/setup blocker, not a confirmed product failure.
- The actual `init_db()` function executed twice against a SQLite backup of the bundled database using a minimal Flask import shim. SQLite `quick_check` was `ok`; foreign-key check returned zero violations; original users, inventory, movements, and vendor records were retained (IDs and stable inventory fields/quantities preserved); the legacy shared notification read flag was normalized and per-account markers were created. No command pointed at the original DB file.
- No live Flask server, PostgreSQL server, or actual SMTP account is available in the assistant preparation runtime.

## Capstone-specific verification scope

The defense target is local Windows + SQLite. Do not block the capstone on Docker, PostgreSQL staging, Waitress, hosted deployment, or a CI/CD pipeline. `requirements-capstone.txt` contains only the dependencies required for the local app. `requirements.txt` remains available for the optional PostgreSQL/deployment path.

A live browser workflow smoke pass on the defense laptop is still needed for: save/restore/clear drafts; first-login forced password change; 30-minute timeout warning/expiry; image display after upload; CSV/XLSX preview/confirm; and the main stock request + procurement + transfer/maintenance + report flows.

## Latest local verification commands (Windows PowerShell)

Run from the updated project folder:

```powershell
# Existing .venv can be reused; do not create a new one if it already works.
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:APP_ENV = "development"
$env:SECRET_KEY = "local-capstone-test-key-only"
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest --collect-only -q
.\.venv\Scripts\python.exe -m pytest -q
```

Expected collection for this package is **207 tests**. Do not run tests against the bundled database; `tests/conftest.py` creates a temporary SQLite database.

## Exit criteria for defense-ready QA

1. Run the current 207-test suite locally and record the exact result.
2. If any test fails, diagnose whether it is a product defect or a stale test expectation; fix only the relevant code/test and rerun.
3. Complete the manual browser walkthrough in `DEFENSE_DEMO_GUIDE.md` on the actual defense laptop.
4. Verify that the existing SQLite data file and records remain intact after startup migrations.
5. Record SMTP as not configured if no real demo mailbox is available; in-app notifications must still be shown live.
6. Update statuses above only from actual current-revision test evidence.

**No requirement is marked fully Verified solely because implementation exists.**

### Targeted follow-up fix — Inventory modal close buttons (2026-11-13)

- The Add Inventory Item and Stock Movement modal X controls now use the shared `data-ui-modal-close` handler instead of closing inline before the asynchronous unsaved-changes prompt can resolve. The Add Item Cancel control uses the same managed close path.
- The shared handler now owns clean closes as well as dirty-form confirmation for these explicitly managed controls. `Continue Editing` leaves the modal and entered values intact; `Discard Changes` resets the form and closes it.
- `openItemModal` / `closeItemModal` also synchronize `aria-hidden` with the visible state.
- Verification performed: `node --check` for `app.js` and `unsaved-changes.js`, Python compilation, and Jinja parsing of all 24 templates passed. A headless Chromium interaction attempt timed out in this environment; the live browser interaction remains to be confirmed on the defense laptop.

### Targeted navigation enhancement — Back button and left drawer control (2026-11-13)

- Added a global Back control beside the page heading on every authenticated page using the shared base template.
- The Back control uses an account-scoped `sessionStorage` trail (last 50 in-tab page locations), returns to the previous in-app page when available, and falls back to Dashboard when a page is opened directly. It does not alter Flask routes, role checks, or page permissions.
- Moved the drawer toggle from the right-side action cluster to the left header controls, immediately beside Back. It remains available while the drawer is collapsed and only opens/closes the drawer; it does not navigate away from the current page.
- Kept the existing drawer scrim, close button, Escape handling, focus behavior, and link behavior. Header controls use existing theme tokens and responsive sizing for light/dark mode and mobile layouts.
- Added a focused source-level regression test for global rendering, history fallback, and control placement.
- Runtime/browser acceptance remains pending in the defense browser; the preparation environment cannot run the full Flask suite because Flask/Werkzeug are not installed.

### Targeted follow-up fix — Inventory item deletion (2026-11-13)

- Expanded the delete endpoint's relationship checks to cover asset disposals, stock adjustments, asset transfers/returns, and maintenance history in addition to movements, requests, assignments, audits, and purchase requisitions. This prevents unhandled foreign-key failures and preserves operational history.
- Newly created or imported items can be permanently deleted when their only movement rows are the one-time `Opening stock` / `Bulk import opening stock` entries. Those setup-only rows are removed in the same database transaction. Any later stock movement still blocks deletion.
- Synthetic forecast demo rows are removed with the item; they are separate from real stock history.
- Delete controls now appear for both Super User and Admin, matching the backend permission policy. The browser handler now handles JSON and non-JSON server responses and surfaces useful error messages.
- Added regression coverage for deleting unused items, deleting items with only opening stock, and protecting items linked to disposal, adjustment, transfer, or maintenance records. Existing transaction-history protection remains in place.
- Verification performed: Python compilation, JavaScript syntax validation, and Jinja parsing of all 24 templates passed; pytest collection reports 207 tests. The full test suite could not execute in this preparation environment because Flask is not installed (`ModuleNotFoundError: No module named 'flask'`). Live browser verification remains to be completed on the Windows defense machine.
