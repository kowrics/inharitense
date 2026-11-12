# ECMCI audited deletion update

- Delete is restricted to Super User by both Flask route policy and the visible button.
- A themed confirmation modal replaces browser `confirm()` and requires a 10–1000 character deletion reason.
- Every successful removal atomically writes `inventory_deletion_logs` (full item snapshot, linked record counts, actor, time, reason) and the existing `audit_logs` entry.
- **Important data-retention detail:** When an item has linked operational history, it is removed from active inventory via a retained tombstone (`deleted_at`, `deleted_by`, `deletion_reason`), **not physically purged**. This is intentional: deleting its database row would break foreign keys and destroy audit traceability. Unlinked items are physically deleted after recording the standalone audit snapshot.
- Historical reports may still contain deleted items because the underlying references are deliberately retained. The active Inventory page excludes deleted items.
- Existing local database data is not overwritten by the patch; the new columns/table are added automatically on next launch.
- The bundled `inharitense.db` is demonstration data, not the user's live local database. Back up the local database before replacing the application code.
