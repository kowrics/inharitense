# ECMCI Client Requirements — Capstone Demonstration Build

**Baseline:** Latest v11 Figma-integrated project, extended for the QA findings.  
**Purpose:** Academic capstone demonstration, not a commercial production release.

## Implemented system areas

- Centralized inventory record management, stock-in/out, movement history, item tags/codes, category handling, and image attachments.
- Role-based navigation and server-side authorization for the eight current/legacy role labels: Super User, Admin, Inventory Manager, Encoder, Requisition Officer, Finance, Report Generator, and Employee.
- Stock requests, review, approval, rejection, and controlled fulfillment with atomic stock protection.
- Asset assignments and employee acknowledgement; transfer/return records with request and completion personnel/timestamps.
- Physical Inventory audit creation, database-backed draft counts, finalization, and pending stock-adjustment proposals requiring Inventory Manager approval.
- Disposal requests with Finance approval. Decisions are audited; stock is deducted only after approval.
- Maintenance records with condition updates and recorder/timestamp history; successful save returns to Maintenance, and owner-scoped maintenance drafts can be saved, reopened, or cleared separately from submitted records.
- Purchase requisitions, approval, purchase-order recording, supplier selection, partial/full receiving, and accepted/rejected quantity tracking. Only accepted delivered units are added to stock.
- Dashboard, demand forecasting, inventory reports, generated downloadable PDF reports (including requisitions and the live Client Reports overview), detailed XLSX/CSV exports, and audit trail with a single Excel/PDF export menu.
- Phase 1 account controls: generated one-time temporary passwords, forced first-login password change, immutable registered email through Account Settings, password visibility controls, mismatch validation, and 30-minute inactivity expiration.
- Account-specific notification read markers, unread count, individual read action, explicit Mark All as Read, workflow-target navigation, request/approval/status notifications, low-stock/out-of-stock notifications, optional SMTP email, duplicate alerts, and per-account request throttling.
- Shared unsaved-change prompts for dirty forms/modals, with Continue Editing and Discard Changes; selected longer-form drafts remain browser-local, while Physical Inventory and Maintenance drafts are database-backed and resumable.
- Inventory image upload for JPEG/PNG/WebP up to 2 MB.
- CSV/XLSX bulk inventory import with preview, row validation, exact duplicate checks, 200-row/5 MB limits, all-or-nothing confirmation, and opening-stock movement records.

- Synthetic demand-forecasting history is visibly marked as demo data and stored separately from actual inventory movement history; it does not change on-hand balances.
- Physical Inventory finalization validates that at least one count exists and required quantity/discrepancy information is complete before posting.

## Capstone implementation boundaries

1. Browser-local drafts are scoped by account ID and browser storage. They do not synchronize across devices. Passwords, CSRF values, and file controls are not saved.
2. Email delivery uses optional SMTP settings. In-app notification functionality is independent and works without an external mail account.
3. Duplicate detection is exact case-insensitive matching for inventory name, item tag, or code. It does not attempt fuzzy similarity matching.
4. The inventory item record is the tracked stock unit. Asset transfers/returns are quantity-level records and do not constitute a complete serialized per-device custody ledger.
5. Procurement in scope includes internal PR approval, PO records, supplier selection, and receiving. External purchasing negotiation, payment processing, and supplier accounting remain outside the application's transaction boundary.
6. The defense setup uses local SQLite. PostgreSQL support remains in the codebase as an optional path but is not required by the panel demonstration.
7. The provisional GL category for Pantry Utensils remains `Pantry Other`, pending any final paper/client-specific mapping decision.

## Demo preparation

Use `README.md` for local setup and `DEFENSE_DEMO_GUIDE.md` for the recommended presentation walkthrough. Keep a backup of the exact SQLite database used during rehearsal. The application performs additive startup migrations and does not reset the database.

## QA evidence

See `QA_PROGRESS.md` for the original 22-requirement matrix plus the supplementary client QA matrix and `FINAL_QA_REPORT.md` for executed checks, limitations, and the latest test commands. Requirements are not marked QA-complete solely because code exists; the latest full test run must pass on the defense package.
