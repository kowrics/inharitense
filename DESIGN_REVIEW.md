# ECMCI v10 — Usability redesign

This version changes presentation only: it retains the v10 backend, routes, data model and POST forms.

Changes:
- The sidebar now has workflow sections and a collapsible inventory category directory.
- The four dense new screens now use accessible tabs, one task at a time.
- Procurement: approvals, create order, receiving, receipt history.
- Asset operations: transfer/return, maintenance entry, transfer history, maintenance history.
- Asset controls: independent requests and approval queues; role-aware tab labels.
- Detailed exports: export configuration separated from record counts.
- Responsive spacing, scrollable tables, keyboard arrow navigation, and print fallback.

The dashboard, existing routes, original database and role checks are not replaced.

## Still to address
The old v9 legacy pages (Inventory, Requests, etc.) need a further usability audit. These changes are not a claim that all client requirements are implemented or that end-to-end tests passed.
