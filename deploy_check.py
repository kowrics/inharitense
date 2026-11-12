"""Deployment readiness checker for the INHARITENSE inventory system.

Run this after `pip install -r requirements.txt`, with the same environment
variables you intend to deploy with (source your .env first, e.g.
`export $(grep -v '^#' .env | xargs)` on Linux/macOS).

    python deploy_check.py

Every check prints one of:
    PASS  - looks correct
    WARN  - not necessarily wrong, but worth a human's attention
    FAIL  - will cause incorrect or insecure behavior; fix before deploying

Exits with status code 1 if any check FAILs, so it can be used as a CI gate.
"""
from __future__ import annotations
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS: list[tuple[str, str, str]] = []  # (status, name, detail)


def check(name, status, detail=''):
    RESULTS.append((status, name, detail))


def section(title):
    print(f'\n== {title} ==')


# ---------------------------------------------------------------------------
# 1. Required files present
# ---------------------------------------------------------------------------
section('Project files')
required_files = ['app.py', 'requirements.txt', 'Dockerfile', 'docker-compose.yml',
                   '.env.example', 'README.md']
for f in required_files:
    ok = (ROOT / f).exists()
    check(f'file present: {f}', 'PASS' if ok else 'FAIL',
          '' if ok else f'{f} is missing from the project root.')

app_source = (ROOT / 'app.py').read_text() if (ROOT / 'app.py').exists() else ''

# ---------------------------------------------------------------------------
# 2. Required Python packages actually importable
# ---------------------------------------------------------------------------
section('Python packages')
REQUIRED_PACKAGES = ['flask', 'werkzeug', 'openpyxl', 'waitress']
for pkg in REQUIRED_PACKAGES:
    found = importlib.util.find_spec(pkg) is not None
    check(f'package installed: {pkg}', 'PASS' if found else 'FAIL',
          '' if found else f'Run: pip install -r requirements.txt (missing {pkg}).')

database_url = os.environ.get('DATABASE_URL', '').strip()
is_postgres = database_url.startswith(('postgres://', 'postgresql://'))
psycopg_found = importlib.util.find_spec('psycopg') is not None
if is_postgres:
    check('package installed: psycopg', 'PASS' if psycopg_found else 'FAIL',
          '' if psycopg_found else 'DATABASE_URL points at PostgreSQL but psycopg is not installed.')
else:
    check('package installed: psycopg', 'PASS' if psycopg_found else 'WARN',
          '' if psycopg_found else 'Not installed, and DATABASE_URL is not set to PostgreSQL yet '
                                    '(fine for SQLite-only dev, required before Postgres deployment).')

# ---------------------------------------------------------------------------
# 3. Environment variables
# ---------------------------------------------------------------------------
section('Environment variables')
app_env = os.environ.get('APP_ENV', 'development').lower()
is_production = app_env == 'production'
check('APP_ENV', 'PASS', f'APP_ENV={app_env!r}')

secret_key = os.environ.get('SECRET_KEY', '')
if is_production:
    weak_defaults = {'', 'inharitense-dev-secret-change-me', 'change-me', 'secret'}
    if not secret_key:
        check('SECRET_KEY set (production)', 'FAIL', 'SECRET_KEY is required when APP_ENV=production.')
    elif secret_key.strip().lower() in weak_defaults or len(secret_key) < 16:
        check('SECRET_KEY set (production)', 'FAIL', 'SECRET_KEY is missing, a placeholder, or too short (use a long random value).')
    else:
        check('SECRET_KEY set (production)', 'PASS')
else:
    check('SECRET_KEY set (production)', 'PASS', 'APP_ENV is not production; the app falls back to a dev-only secret.')

if is_production:
    check('DATABASE_URL set (production)', 'PASS' if database_url else 'WARN',
          '' if database_url else 'No DATABASE_URL set; the app will fall back to local SQLite in production, '
                                   'which is not recommended for a multi-user deployment.')
    for var in ('BOOTSTRAP_ADMIN_EMAIL', 'BOOTSTRAP_ADMIN_PASSWORD'):
        val = os.environ.get(var, '')
        check(f'{var} set', 'PASS' if val else 'WARN',
              '' if val else f'{var} is not set. If the users table is empty, production startup will fail '
                              f'until this is set (by design, so a real admin account is always required).')
else:
    check('DATABASE_URL set', 'PASS' if database_url else 'WARN',
          '' if database_url else 'Not set; SQLite (inharitense.db) will be used for local development.')

# ---------------------------------------------------------------------------
# 4. Database connectivity + schema
# ---------------------------------------------------------------------------
section('Database')
REQUIRED_TABLES = ['users', 'inventory', 'movements', 'requests', 'vendors', 'audit_logs', 'notifications']
db_ok = False
try:
    if is_postgres:
        if not psycopg_found:
            raise RuntimeError('psycopg not installed')
        import psycopg
        conn = psycopg.connect(database_url, connect_timeout=5)
        cur = conn.execute('SELECT 1')
        cur.fetchone()
        conn.close()
        check('database connectivity', 'PASS', 'Connected to PostgreSQL via DATABASE_URL.')
        db_ok = True
    else:
        import sqlite3
        db_path = Path(os.environ.get('SQLITE_DB_PATH') or (ROOT / 'inharitense.db'))
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute('SELECT 1')
        conn.close()
        check('database connectivity', 'PASS', f'Connected to SQLite at {db_path}.')
        db_ok = True
except Exception as e:
    check('database connectivity', 'FAIL', f'Could not connect to the database: {e}')

# ---------------------------------------------------------------------------
# 5. WSGI import / startup (this also runs init_db(), so it is the real schema-
#    initialization test — importing app.py is exactly what waitress-serve does)
# ---------------------------------------------------------------------------
section('Application startup')
flask_app = None
if importlib.util.find_spec('flask') is not None:
    try:
        spec = importlib.util.spec_from_file_location('inharitense_app', ROOT / 'app.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # this runs init_db() for real, same as a normal boot
        flask_app = module.app
        check('app imports and initializes (app:app)', 'PASS',
              'waitress-serve --listen=0.0.0.0:8000 app:app will find a valid WSGI app object.')
    except Exception as e:
        check('app imports and initializes (app:app)', 'FAIL', f'{type(e).__name__}: {e}')
else:
    check('app imports and initializes (app:app)', 'FAIL', 'Flask is not installed; cannot import app.py.')

if db_ok:
    try:
        if is_postgres:
            import psycopg
            conn = psycopg.connect(database_url, connect_timeout=5)
            existing_after = {r[0] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'").fetchall()}
            conn.close()
        else:
            import sqlite3
            db_path = Path(os.environ.get('SQLITE_DB_PATH') or (ROOT / 'inharitense.db'))
            conn = sqlite3.connect(str(db_path), timeout=5)
            existing_after = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
        missing_tables = [t for t in REQUIRED_TABLES if t not in existing_after]
        if missing_tables:
            check('required tables present (after init)', 'FAIL',
                  f'Still missing after startup: {", ".join(missing_tables)}. Schema initialization failed.')
        else:
            check('required tables present (after init)', 'PASS', f'All {len(REQUIRED_TABLES)} expected tables exist.')
    except Exception as e:
        check('required tables present (after init)', 'FAIL', f'Could not verify schema: {e}')
else:
    check('required tables present (after init)', 'WARN', 'Skipped: no database connection.')

if flask_app is not None:
    check('debug disabled', 'PASS' if flask_app.config.get('DEBUG') is not True else 'FAIL',
          '' if flask_app.config.get('DEBUG') is not True else 'Flask DEBUG is True — never run this in production.')
    cookie_secure = flask_app.config.get('SESSION_COOKIE_SECURE')
    if is_production:
        check('secure session cookie (production)', 'PASS' if cookie_secure else 'FAIL',
              '' if cookie_secure else 'SESSION_COOKIE_SECURE is not True in production; session cookies '
                                        'could be sent over plain HTTP.')
    else:
        check('secure session cookie', 'PASS', f'SESSION_COOKIE_SECURE={cookie_secure} (expected False outside production).')
    check('session cookie httponly', 'PASS' if flask_app.config.get('SESSION_COOKIE_HTTPONLY') else 'FAIL')
else:
    check('debug disabled', 'WARN', 'Skipped: app did not import.')
    check('secure session cookie', 'WARN', 'Skipped: app did not import.')

# Source-level checks that don't need a successful import, kept as a fallback safety net.
check('csrf protection present (source)', 'PASS' if 'Invalid or missing CSRF token' in app_source else 'FAIL')
check('postgres support present (source)', 'PASS' if 'psycopg' in app_source else 'FAIL')
check('transaction history protected (source)', 'PASS' if 'cannot be deleted. Archive it instead.' in app_source else 'FAIL')
check('demo/seed data gated to non-production (source)', 'PASS' if 'not IS_PRODUCTION' in app_source else 'FAIL')
check('production requires SECRET_KEY (source)', 'PASS' if 'SECRET_KEY must be set in production' in app_source else 'FAIL')

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section('Summary')
counts = {'PASS': 0, 'WARN': 0, 'FAIL': 0}
width = max(len(name) for _, name, _ in RESULTS)
for status, name, detail in RESULTS:
    counts[status] += 1
    line = f'{status:5} {name.ljust(width)}'
    if detail:
        line += f'  \u2014 {detail}'
    print(line)

print(f"\n{counts['PASS']} passed, {counts['WARN']} warnings, {counts['FAIL']} failed.")
if counts['FAIL']:
    print('\nFix the FAIL items above before deploying to production.')
    sys.exit(1)
elif counts['WARN']:
    print('\nNo failures, but review the WARN items above.')
else:
    print('\nAll checks passed.')
