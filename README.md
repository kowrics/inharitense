# ECMCI Integrated Inventory Management System

**Capstone demonstration build · v11 Figma-integrated UI**

This project is prepared for an academic capstone defense. It is intended to run locally on a Windows laptop using the bundled SQLite database. The current sage-green/white Figma-integrated interface and existing inventory, approval, procurement, forecasting, and reporting workflows are retained.

## 1. Run the system on the defense laptop

### Requirements

- Windows 10/11
- Python 3.12 or 3.13
- Internet access for the first dependency installation only (unless the packages are already installed)
- A browser such as Chrome or Edge

### Start

1. Extract the ZIP into a **new folder** such as `C:\ECMCI-Capstone` (do not extract over the old project folder).
2. Keep the included `inharitense.db`. If your existing rehearsal folder contains a newer database with records you want to retain, back it up and copy that database into the new folder, replacing the bundled copy only after you have verified the backup.
3. Double-click `run.bat`.
4. The first launch creates a project-local `.venv` and installs only the capstone runtime dependencies from `requirements-capstone.txt`.
5. Open `http://127.0.0.1:5000` in the browser.

The launcher selects local SQLite mode and never resets or replaces `inharitense.db`. Startup migrations are additive and run automatically. **Do not delete the database to solve a startup issue.** Make a copy before trying migrations or test data operations.

To stop the server, focus the command window and press `Ctrl+C`.

### Install/test manually

PowerShell, from the project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
$env:APP_ENV = "development"
$env:SECRET_KEY = "local-test-only-secret-change-me"
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
python -m pytest --collect-only -q
python -m pytest -q
```

If Python 3.12 is unavailable, use `py -3.13`. If PowerShell blocks activation, use the venv interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The test fixture creates its own temporary SQLite database. It must not use or reset the bundled `inharitense.db`.

## 2. Demonstration accounts

These are local demo credentials for the capstone copy only. Change passwords during preparation if the panel requires it; do not publish these credentials or expose the demo server to the public internet.

| Role | Email | Initial demo password |
|---|---|---|
| Super User / System Administrator | `admin@ecmci.com` | `admin123` |
| Encoder | `encoder@ecmci.com` | `encoder123` |
| Report Generator | `reports@ecmci.com` | `report123` |
| Employee | `employee@ecmci.com` | `employee123` |

The project also supports Admin, Inventory Manager, Requisition Officer, and Finance roles. Create those through Users for a demonstration; newly created accounts receive a one-time temporary password and are required to change it at first sign-in.

If the included database has legacy demo accounts, the local development startup migration maps them to the current demo email/role conventions while retaining their user IDs and linked records. Existing non-demo accounts are not recreated.

## 3. Main functionality

- Centralized inventory records, category views, tags/codes, stock-in/out, and movement history.
- Stock requests with review, approval, and controlled fulfillment.
- Assignment and employee acknowledgement; transfer/return records with confirmation details.
- Physical inventory audits with saved drafts and manager-approved stock corrections.
- Disposal requests with Finance approval.
- Maintenance recording, condition updates, and maintenance history.
- Purchase requisitions, approval, purchase order creation, supplier selection, and receiving. Accepted quantities update inventory; rejected quantities are recorded but are not added to stock.
- Demand forecasting from recorded stock usage, with clearly identified synthetic history isolated in a separate demo-only table for presentation.
- Dashboard, inventory reports, generated PDF downloads (including the Client Reports overview and requisitions), Excel/CSV exports, and audit history. Audit Trail provides Excel/PDF from one Export Movements menu.
- Account-specific notification read status, unread badge, low-stock alerts, duplicate-entry alerts, and request submission throttling.
- Inventory item image upload and CSV/XLSX bulk stock import with preview/validation.
- Browser-local drafts for selected forms; Physical Inventory and Maintenance drafts are database-backed and can be resumed by their owner. Shared unsaved-change prompts protect dirty forms and modal values.

For a guided panel walkthrough, see `DEFENSE_DEMO_GUIDE.md`.

## 4. Capstone feature limits / honest scope

The current package includes 207 collected automated tests. The full latest suite must still be run on the Windows defense laptop using the commands below; a test collection alone is not a passing suite. The QA matrix records what has been implemented separately from what has actually been executed.

- Browser form drafts are stored in `localStorage` for the current account and browser/device. They are not synchronized across devices. The existing Physical Inventory draft workflow is database-backed.
- In-app alerts work without external services. Actual email delivery is optional and requires SMTP settings; the demo does not depend on a third-party email service.
- Low-stock and duplicate alerts are sent to active accounts in the relevant system roles. Duplicate checks are exact case-insensitive item name/tag/code checks; the system does not perform fuzzy or AI similarity matching.
- CSV/XLSX bulk import is limited to 200 records and 5 MB per file. Import is previewed and committed as one transaction; opening stock is recorded in movement history.
- Inventory image uploads support JPEG, PNG, and WebP, up to 2 MB each.
- Asset circulation records are quantity-level transaction records. This version does not provide a complete unique-serial-number custody ledger for every physical asset.
- Procurement in the system covers internal requisition preparation/approval, purchase-order recording, supplier selection, and delivery receiving. Supplier negotiation, payments, and external accounting transactions remain outside the application.
- The local SQLite setup is the recommended defense configuration. PostgreSQL support remains available in the codebase but is not required to run the capstone demonstration. Optional deployment dependencies are in `requirements.txt`; the local app uses `requirements-capstone.txt`.

## 5. Optional email notification setup

In-app notifications always work. To test actual outgoing email, set SMTP variables in the same PowerShell window before launching `run.bat`:

```powershell
$env:SMTP_HOST = "smtp.example.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "your-demo-account@example.com"
$env:SMTP_PASSWORD = "your-app-password"
$env:SMTP_FROM = "your-demo-account@example.com"
$env:SMTP_STARTTLS = "1"
.\run.bat
```

Use a dedicated demo mailbox and app password. Do not put email credentials in source code or commit them. If SMTP is not configured, the system logs the unavailable email transport while keeping the in-app notification.

## 6. Database safety

- The bundled SQLite file contains demo/project data and is not reset by `run.bat`.
- Make a copy of `inharitense.db` before switching packages or experimenting with migrations.
- Never delete the database to make a feature appear; use the normal startup migrations.
- The tests use an isolated temporary database (`SQLITE_DB_PATH`) and should not touch your demo database.
- Backups can be created with `python backup.py` from the project folder.

## 7. Troubleshooting

| Problem | Recommended action |
|---|---|
| `python` or `py` not found | Install Python 3.12/3.13 and reopen PowerShell. |
| Package installation fails | Confirm internet access or install the four packages in `requirements-capstone.txt` into `.venv`. |
| Port 5000 is in use | Stop the other local app, or edit `PORT` in `run.bat` and use the matching browser URL. |
| Login does not work | Check the account email/password table above; a newly created user must change the temporary password first. |
| Import fails | Use the sample CSV template; check allowed categories, whole-number quantities, duplicate names/tags/codes, 5 MB size, and 200-row limit. |
| Image upload fails | Use a real JPEG, PNG, or WebP image no larger than 2 MB. |
| Notifications do not send email | Configure the optional SMTP variables; in-app notifications do not require SMTP. |

## 8. Project verification

`QA_PROGRESS.md` tracks all 22 numbered QA requirements and distinguishes implementation from executed verification. `FINAL_QA_REPORT.md` records the current test-environment limitations and exact local verification steps. Do not present an automated test as passed unless the corresponding command completed successfully on the current project revision.
