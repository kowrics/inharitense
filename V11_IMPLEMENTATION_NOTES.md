# ECMCI v11 — client-process implementation (development build)

Built from ECMCI_v10_Actual_UI_Redesign_FIXED.zip. Original v10 remains unchanged. This is not a fully certified client-ready build.

## Added in v11
- Finalized physical-count variances now automatically create pending stock-adjustment proposals requiring Inventory Manager approval. No stock change occurs when the count is finalized; the prior approval screen applies guarded, audited changes.
- Existing inventory edit, stock-in/out, and physical count access now honor Admin and Inventory Manager roles consistently with the navigation policy; old accounts remain valid.
- Client detailed report downloads now support a generated PDF (.pdf), in addition to XLSX and CSV. PDF data is partitioned into printable column blocks to avoid clipping.
- Report filters additionally accept department/custody (where applicable) and employee ID (where applicable).
- Added ReportLab as an application dependency for the PDF report.

## Known limits / remaining implementation
- This release does NOT include a full unique-per-physical-unit asset registry. Inventory tags remain associated with inventory item records.
- Department transfers/returns are transaction records, not a per-asset custody ledger.
- Some stock count, purchasing, assignment, and supplier-related UI and role policies need full end-to-end testing.
- Reports are mostly raw dataset exports; polished financial/custody/discrepancy summaries and richer period filters need more work.
- The client's GL mapping omits Pantry Utensils; the system's existing provisional 'Pantry Other' assignment is not client-confirmed.
- Direct stock-in/out operations remain available to authorized personnel; these must be used for actual movements/issuance, not as a workaround for stock count correction approvals.
- Automated email requires SMTP configuration; live credentials and production alerts were not tested.
- Browser integration/regression tests could not run in the current environment because Flask/Werkzeug were not installed and package download was unavailable. Code compilation, Jinja parse, SQLite integrity, and archive tests were performed.

## Start safely
1. Extract to a NEW folder. Keep your prior ZIP and database backup.
2. Windows: run `run.bat` with internet access for dependency installation (ReportLab newly required).
3. Use the new Client Reports PDF export; finalize an inventory count with a discrepancy, then review the pending proposal in Asset Controls & Approvals as Inventory Manager.
4. Before production: validate every role and workflow on a staging copy, and rotate demo credentials.
