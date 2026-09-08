# INHARITENSE — Integrated Inventory Management System

A Flask + SQLite implementation of the ECMCI healthcare BPO inventory workflow.

## Run
1. Install Python 3.10+.
2. Double-click `run.bat`.
3. Open `http://127.0.0.1:5000`.

Manual:
```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py app.py
```

## Demo accounts
- HR / Admin: `hr@ecmci.com` / `hr123`
- Purchasing / Procurement: `purchasing@ecmci.com` / `purchase123`
- IT Custodian: `it@ecmci.com` / `it123`
- Department Employee: `employee@ecmci.com` / `employee123`

## Included
- Session authentication and role-based access
- HR-controlled users and audit trail
- Inventory CRUD with duplicate prevention
- Stock IN / OUT with database transaction history
- Live dashboard analytics polling the database every 5 seconds
- Inventory health and category charts
- Requests: Department → Purchasing → HR → Fulfillment
- Vendor masterlist for Purchasing
- Forecast using recent Stock OUT history
- Replenishment indicators
- CSV and Excel exports
- Notification inbox
- QR/bar-code lookup and camera scanner where browser support is available
- Light/dark theme

The first run seeds sample inventory, vendors, accounts, and clearly labeled demo movement history so the dashboard charts are populated. New transactions are real database records and update the analytics automatically.

## Production note
This is a local full-system build for the project/prototype stage. Before deployment, set a strong `SECRET_KEY`, use a production WSGI server, HTTPS, stronger password policies, CSRF protection, database backups, and real email/notification infrastructure.
