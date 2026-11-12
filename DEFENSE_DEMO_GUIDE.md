# ECMCI Capstone Defense — Demonstration Guide

This guide is designed for a 10–15 minute live walkthrough. It uses the local SQLite demonstration setup and avoids depending on external services.

## Before the panel

1. Extract the final ZIP into a new folder; do not overlay it on top of the old project. If your old rehearsal folder has a newer `inharitense.db`, back it up and copy it into the new folder after extraction.
2. Make a backup using `python backup.py` and keep a separate copy of `inharitense.db`.
3. Run `run.bat` and open `http://127.0.0.1:5000`.
4. Check that the Dashboard loads, the notification badge responds, and the theme toggle works.
5. Sign into each required role once before the defense so passwords and session states are known.
6. Create a small set of clearly named demo records (prefix them with `DEMO-`) rather than modifying important existing sample records.
7. For image upload, prepare a real small PNG/JPG/WebP file. For bulk import, prepare a CSV with 2–3 distinct sample items.

## Demo accounts

| Role | Email | Demo password |
|---|---|---|
| Super User / System Administrator | `admin@ecmci.com` | `admin123` |
| Encoder | `encoder@ecmci.com` | `encoder123` |
| Report Generator | `reports@ecmci.com` | `report123` |
| Employee | `employee@ecmci.com` | `employee123` |

Admin, Inventory Manager, Requisition Officer, and Finance accounts may be created during preparation. Newly created accounts receive a temporary password; the user must change it on first login. Keep the one-time generated password available for the demonstration.

## Suggested walkthrough

### 1. Login, roles, and security (1–2 minutes)

- Sign in as Super User and point out the dashboard, profile menu, notification badge, and navigation drawer.
- Show Users and the available roles.
- Create a demo account, show the generated temporary password once, then sign in as that user and demonstrate the forced password-change screen.
- Show the password visibility toggle and read-only registered email in Settings.
- Explain that inactivity expires the session after 30 minutes; the warning appears shortly before expiry.

### 2. Inventory and image records (1–2 minutes)

- Open Inventory & Stock.
- Show item tag, category, on-hand quantity, minimum/maximum, condition, custodian, and movement history.
- Create a clearly named `DEMO-` item with an image and opening quantity.
- Explain that changing an item's description does not silently rewrite its stock quantity; stock changes are recorded through movements.

### 3. Stock request and approval (2 minutes)

- Sign in as Employee and submit a request for a demo item.
- Sign in as Encoder to review/endorse according to the existing workflow.
- Sign in as Super User to approve or reject.
- Return to Encoder to fulfill the approved request.
- Show the movement history and resulting on-hand quantity.

### 4. Assignment and asset circulation (1 minute)

- Create an assignment to an active Employee account.
- Sign in as that Employee and acknowledge receipt.
- Open Asset Circulation and show a transfer/return record with requester, confirming personnel, and timestamps.
- Note that this is a quantity-level record, not a serial-number custody ledger for every physical unit.

### 5. Maintenance, correction, and disposal (1–2 minutes)

- Record a maintenance inspection and show the recorded-by/date information.
- Open Physical Inventory, save a partial count as a draft, then resume it.
- Finalize a discrepancy to create a pending stock correction.
- Sign in as Inventory Manager and approve/reject the correction.
- Show the Finance approval path for a disposal request.

### 6. Procurement and receiving (2 minutes)

- Sign in as Requisition Officer or Encoder and create a purchase requisition.
- Sign in as an authorized approver to approve it.
- Create a purchase order and select a supplier.
- Record delivery, including delivered and accepted quantities. To demonstrate partial acceptance, use an example such as 5 delivered, 4 accepted, 1 rejected.
- Show that only the accepted quantity increases inventory and that a receipt and movement record are stored.

### 7. Notifications and low-stock alert (1 minute)

- Use a demo item with a small minimum quantity.
- Record a stock-out that crosses the minimum.
- Show the in-app low-stock notification and numerical unread badge.
- Open one notification to mark only that item read. Explain that opening the panel does not mark everything read and that Mark All as Read is a separate action.
- If a demo SMTP mailbox is configured, show email delivery. If not, demonstrate the in-app alert and explain SMTP as an optional notification transport.

### 8. Forecast, generated PDFs, and export menu (1–2 minutes)

- Open Demand Forecasting and choose an item with seeded `[DEMO SAMPLE]` history. Explain that the synthetic forecast movements are stored in a separate demo table and do not change on-hand stock or the actual movement ledger.
- In Client Reports, use the overview PDF action and confirm the browser downloads a generated report containing live record counts/statistics rather than printing the current page.
- Open a Purchase Requisition record and use its PDF download. On Audit Trail, open Export Movements and choose Excel or PDF from the compact menu.
- If the panel asks how a report is built, explain that the application creates a report document from database records and sends it as a file attachment.

## 9. Unsaved changes, drafts, and maintenance (1 minute)

- Open a supported data-entry form, enter a harmless demo value, and attempt to close it. Select Continue Editing to preserve the draft in the form, then repeat and choose Discard Changes.
- Open Maintenance, save a sample record, and confirm the user stays in the Maintenance view.
- Save a Maintenance draft and show the Drafts list. Reopen it to continue editing; clear it only after the confirmation prompt. Explain that a saved draft and a submitted maintenance record are separate objects.
- In Physical Inventory, try to finalize an empty/incomplete audit and show the row-level required-field message before completing a demo count.

## 10. Bulk import and reporting (1–2 minutes)

- Download the inventory import template.
- Upload a 2–3-row CSV or XLSX file.
- Show preview/validation and confirm the import.
- Show that imported opening quantities have movement records.
- Open reports and generate XLSX/CSV/PDF exports.
- Show forecasting and audit trail as appropriate for the panel's questions.

## What to say about notification/draft/import limits

- In-app notifications work locally; email requires an SMTP account and network access.
- Most form drafts are stored in the current browser and account on the same device. Physical Inventory drafts are stored in the application database.
- Bulk import supports CSV/XLSX, up to 200 rows and 5 MB per file. It previews and validates all rows before a single all-or-nothing save.
- Image files are JPEG/PNG/WebP, up to 2 MB.

## Demo recovery

- If the browser session expires, sign in again. Do not clear browser data if you need local form drafts.
- If a demo request/PO is already completed, use another clearly named demo record; do not edit database rows manually during the presentation.
- If a workflow is accidentally rejected, create a new demo request rather than trying to reverse a recorded approval.
- If the server is stopped, return to the command window and rerun `run.bat`. Do not delete or rename `inharitense.db`.
