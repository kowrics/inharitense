# ECMCI INHARITENSE — v9 final request workflow and forecast demo

See `V9_FINAL_NOTES.md` for the corrected roles, forecast demo instructions, changed files, manual checks, and role matrix. `V9_SOURCE_CHANGES.diff` provides exact replacements against v8 Complete.

## Run locally on Windows

1. Extract this ZIP into a new folder.
2. Double-click `run.bat` (Python 3.10+ required).
3. Open http://127.0.0.1:5000.

| Role | Demo email | Initial password |
|---|---|---|
| Super User | admin@ecmci.com | admin123 |
| Encoder | encoder@ecmci.com | encoder123 |
| Report Generator | reports@ecmci.com | report123 |
| Employee | employee@ecmci.com | employee123 |

Existing edited demo account passwords now survive restarts. Legacy account email addresses are migrated once to the addresses above.

## What changed

- PostgreSQL startup creates the revised inventory columns and safely skips existing category settings on restart.
- Opening stock for new items creates an IN transaction. Existing quantity is read-only in the edit form; later changes use Stock IN / OUT. Item edits cannot overwrite concurrently updated stock.
- Assignments use an atomic stock deduction, require an active Employee, and use collision-resistant reference numbers.
- Request actions serialize updates to prevent repeated concurrent fulfillment of the same request.
- Inventory report preview and CSV share explicit acquisition-date and assignment/legacy custody filters; weekly/monthly periods retain older inventory and select movement dates. Items assigned to multiple departments are clearly labeled.
- Finalized audits are read-only on the server. Counts must be valid and discrepancies explained; every item must be counted before finalization. Saving and finalization create audit log entries.
- Items referenced by assignments, audits, or requisitions cannot be deleted.
- Forecasts use 26 complete Monday-to-Sunday weeks, excluding the current incomplete week. The linear-regression/recent-mean model and insufficient-data behavior remain.
- Existing account names and passwords are preserved on subsequent startup.

## Updating your working copy

The included database is the unchanged database from your uploaded ZIP. If your local system has newer records, stop the running app, back up the entire old folder, and copy its database into this extracted folder before starting. Copy the database only after stopping the app; retain any SQLite WAL/SHM files with your backup until the database is safely closed. Do not overwrite your only working copy.

## Demo workflow

1. Encoder records stock received through Stock IN.
2. Employee submits a request; Encoder reviews and endorses it; Super User approves; Encoder releases stock.
3. Super User or Encoder assigns an item to an Employee; Employee acknowledges receipt.
4. Super User creates and assigns an audit; its Encoder records counts and discrepancy notes, saves drafts, and finalizes it.
5. Report Generator selects a period or department, checks the preview, and exports CSV.
6. Super User or Encoder prepares a requisition report. Forecasting is viewable by Super User, Encoder, and Report Generator; asset lifecycle stays Super User-only.

## Validation and practical limits

162 automated tests pass against an isolated SQLite database. Browser workflows and 80 page/viewport/theme combinations passed with no horizontal page overflow or JavaScript errors. A live PostgreSQL server was unavailable for this update.

The ML model still needs evaluation against actual usage with held-out historical data. R² describes model fit; it is not forecast accuracy. Lifecycle/EOL monitoring uses acquisition dates and useful-life rules. Demo stock history is illustrative and must not be used as evidence of model accuracy or historical balance reconciliation. Existing historical stock inconsistencies were not rewritten.

Run the automated checks with:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```


# Part 2 — Future Production Deployment Requirements

**Not needed for the client demo — read this only after client approval,
when preparing a real deployment.**

## Environment variables for production

Copy `.env.example` to `.env` and fill in real values. Never commit `.env`.

| Variable | Required | Notes |
|---|---|---|
| `APP_ENV` | yes | Set to `production`. This alone switches off all demo-mode behavior described in Part 1. |
| `SECRET_KEY` | **yes** | App refuses to start without it. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `DATABASE_URL` | yes | `postgresql://user:pass@host:5432/dbname`. |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Docker only | Used by `docker-compose.yml` to configure the `db` container. Keep in sync with `DATABASE_URL`. |
| `BOOTSTRAP_ADMIN_NAME` / `_EMAIL` / `_PASSWORD` | first boot only | Creates the first real HR account. Startup fails with a clear error if missing on an empty database. |
| `SMTP_*` | no | Optional email delivery for notifications; in-app notifications work regardless. |

## PostgreSQL

Set `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME` and
`APP_ENV=production`. The app uses `psycopg[binary]` and the same schema/SQL
logic as SQLite through a small compatibility layer (`DBConn` in `app.py`),
including foreign keys, transactions, and atomic stock updates (`UPDATE ...
WHERE qty >= ?` guards prevent negative stock even under concurrent
requests). Verify on your staging PostgreSQL instance before deployment.

## Docker deployment

```bash
cp .env.example .env
# edit .env: SECRET_KEY, POSTGRES_DB/USER/PASSWORD, DATABASE_URL (host must be "db"),
# BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD
docker compose up --build -d
docker compose logs -f web
```

Two containers: `db` (PostgreSQL 16, credentials entirely from `.env`, no
hardcoded passwords) and `web` (`waitress-serve --listen=0.0.0.0:8000
app:app`, with a Docker `HEALTHCHECK` against `/healthz`, which itself
checks real database connectivity).

## HTTPS

In production, `SESSION_COOKIE_SECURE=True` is set automatically, meaning
session cookies are only sent over HTTPS. This is intentional and correct
for a real deployment — but it means production mode needs a TLS-terminating
reverse proxy (nginx, Caddy, a load balancer, or your hosting platform's
built-in HTTPS) in front of the app. Don't set `APP_ENV=production` for an
environment that's only ever going to be plain HTTP.

## Database design note (documented, not yet implemented)

`inventory.vendor` and `inventory.custodian` are free-text columns even
though a `vendors` table already exists. A future safe, non-destructive
migration path:
1. Add a nullable `vendor_id INTEGER REFERENCES vendors(id)` column.
2. Backfill it by matching `inventory.vendor` text to `vendors.name`.
3. Update the inventory form/queries to use `vendor_id`, keeping the
   `vendor` text column for backward compatibility during rollout.
4. Only drop the text column once every read path has migrated.

This project intentionally does not use Alembic/Flask-Migrate yet — the
schema is small and single-file, and `CREATE TABLE IF NOT EXISTS` is
lower-risk at this scale. Revisit if the schema grows substantially.

## Backups

- **SQLite (dev/demo):** `python backup.py` copies `inharitense.db` into
  `backups/` with a timestamp, safe to run while the app is running.
- **PostgreSQL (production):** `backup.py` refuses to run against a Postgres
  `DATABASE_URL` on purpose — schedule `pg_dump` (or your hosting provider's
  managed backups) against `DATABASE_URL` instead.

## Production troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `RuntimeError: SECRET_KEY must be set in production.` | Set `SECRET_KEY` before starting. |
| `RuntimeError: Production database is empty. Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD...` | First production boot against an empty DB needs both set. |
| `psycopg.OperationalError: connection ... refused` | PostgreSQL isn't reachable — check `DATABASE_URL` and that `db` is up/healthy. |
| App connects to `localhost` instead of the `db` container | `DATABASE_URL` must use `db` as the host under Docker Compose, not `localhost`. |
| Login redirects back to `/login` even with correct credentials | `SESSION_COOKIE_SECURE=True` in production means the cookie only sends over HTTPS — you need a TLS-terminating proxy in front of the app, or don't set `APP_ENV=production` for a plain-HTTP-only environment. |
| "Only N ... available" (409) on stock out/fulfillment | Expected — the atomic stock guard preventing negative inventory, most often because a concurrent movement happened first. |
| "Too many failed attempts" (429) | In-memory login lockout after 5 failures from the same IP; clears after 5 minutes or on app restart. |
