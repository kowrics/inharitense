# ECMCI Client Requirements — Incremental Upgrade (Phase 1)

**Baseline:** Uploaded ECMCI Inventory System v9 Final. This is a new working copy; original ZIP is not modified.

## Implemented in this upgrade
- Added `Asset Controls & Approvals` interface and two database tables created automatically on application startup.
- Disposal requests require Finance (or legacy Super User/Admin) approval. An approval verifies available quantity, deducts stock exactly once, logs a movement, and records approver and timestamp. Rejection does not move stock.
- Stock correction requests require Inventory Manager (or legacy Super User/Admin) approval. Approval checks that stock has not changed since request; otherwise it rejects the attempted approval without recording it. Rejections leave stock unchanged.
- Request creation does not alter stock; all decisions produce audit log entries.
- Added client-defined roles (Admin, Inventory Manager, Requisition Officer, Finance) as selectable new account roles **without deleting or rewriting existing legacy users**. They currently have partial permissions only, pending RBAC refactor.
- Existing physical inventory audit remains separate and does not automatically adjust stock. Finalized discrepancies can be submitted manually for manager review through Asset Controls.

## Important limitations — NOT a complete client specification implementation
1. Roles are transitional: existing Super User, Encoder, Report Generator and Employee roles remain. Admin is not yet equivalent to full Super User across every module; Requisition Officer does not yet own full purchase workflows.
2. Existing inventory creation/edit/stock-movement APIs retain v9 behavior. Not every possible stock edit has been routed through the new approval workflow.
3. Disposal here is quantity-based from on-hand inventory; unique serialized asset disposal, maintenance history, asset transfers/returns and reconciliation with individually assigned assets remain future work.
4. Supplier selection, purchase order, purchase approval and receiving process remain as in original v9 (purchase requisitions are preparation/printing only).
5. Existing report sets have not yet been expanded to every required report or filter.
6. Finance and Manager workflows should be validated against your client’s final approval delegation policy.
7. PU (Pantry Utensils) GL category mapping requires client clarification.

## How to run
1. Keep a backup of your original ZIP and `inharitense.db`.
2. Extract this ZIP to a separate directory (do not overwrite the original).
3. Run `run.bat` on Windows; dependencies must be available/internet accessible on the installation machine.
4. Sign in with your existing v9 account. The sidebar will show **Asset Controls & Approvals** for eligible roles.
5. Create Finance and Inventory Manager users under Users & Activity (temporary password is configured in `.env` / `DEFAULT_TEMP_PASSWORD`; change before production).
6. Always test with dummy inventory and accounts first; work from a backup of the DB.

## Test status
- Python syntax compilation: passed.
- Existing pytest suite: unable to execute in this sandbox because Flask is not installed and the environment cannot reach package repositories. Full application and UI behavior **not verified**.
