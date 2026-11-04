# ECMCI Client Requirements — Expanded Working Version (v10 Preview)

This package is built from the actual user-supplied ECMCI Inventory System v9 Final and the Phase 1 controls upgrade. The uploaded source ZIP remains unchanged.

## Included / newly added
- Five client-defined roles selectable in user creation (Admin, Inventory Manager, Encoder, Requisition Officer, Finance). Legacy Super User, Employee and Report Generator roles are kept to avoid breaking existing accounts.
- Asset Controls from Phase 1: Finance-approved disposal and Inventory Manager-approved stock adjustments; audit logs and guarded inventory updates.
- Procurement & Receiving: requisition approval/rejection; one supplier purchase order per approved, item-linked PR; order status tracking; partial deliveries; delivered/accepted/rejected quantities; only accepted quantities raise on-hand stock; audit record and movement record.
- Transfers & Maintenance: request and confirm department/location transfer/return without changing global stock totals; record inspection, repair and damage events with condition, cost, and date.
- Client Reports: eleven export datasets as XLSX or CSV, optionally filtered by date/category/status where supported, alongside existing print-to-PDF reports.
- Existing inventory, item tags, dashboard, forecasting, requests, assignments, physical audits, supplier management, notifications, and legacy reporting preserved.
- Additive SQLite/PostgreSQL schema migration to create new tables and approval metadata; existing database not intentionally reset.

## Important remaining gaps and client decisions
**Not claimed to be 100% production-complete or end-to-end verified.** The app's dependencies are not installed in the build sandbox, so real Flask login/routes/UI/end-to-end tests could not be executed. Test on a copy of the database before use.

1. The document does not say who may approve purchase requisitions. This preview delegates approval to Admin/Inventory Manager/Super User, pending written client confirmation.
2. Unlinked requisitions may be prepared and approved but cannot automatically generate a receiving PO until linked to an existing inventory item. No auto-creation of brand-new inventory item on receiving.
3. Transfers are department/location *custody history*; they do not link to a unique serialized-asset physical location ledger or fully reconcile existing assignment acknowledgements.
4. Existing v9 stock-edit and stock in/out APIs remain; not all direct corrections are forced through approval. Full policy hardening is still required.
5. New client reports supply Excel/CSV datasets and legacy browser-print reports. Full styled, per-report native PDF generation, monthly/quarterly filters, and all department/employee joins are not yet implemented.
6. PU / Pantry Utensils has a provisional "Pantry Other" GL mapping in v9, while the supplied client process excludes PU from its GL grouping list. Confirm correct accounting mapping.
7. Full permission reconciliation across *every* legacy endpoint and UI panel, security review, use-case testing, automated tests, and deployment hardening remain needed.
8. Client-approved maintenance/disposal lifecycle constraints for individually tagged assets must be finalized.

## Run
1. **Back up your original ZIP and `inharitense.db` first.** Do not extract this package over a working deployment.
2. Extract into its own new folder, e.g. `ECMCI_Client_Expanded_v10`.
3. Run `run.bat`, allow it to install dependencies if needed, then open the displayed local URL.
4. Use your existing v9 demo login; create other roles through Users & Activity.
5. Try one test purchase requisition linked to an existing inventory item, approve it in Procurement & Receiving, select an active vendor, create the purchase order, and receive a partial delivery with accepted quantity.
6. Review Transfers & Maintenance, Asset Controls, and Client Reports.
7. Keep real inventory out of the test until the client confirms the workflow and testers verify permissions and balances.

## Static checks performed
- Python syntax compilation: passed.
- SQLite schema DDL creation: passed.
- SQLite database integrity on the user's bundled copy: checked separately.
- Automated Flask/UI/end-to-end and PostgreSQL migration execution: NOT performed in build environment.
