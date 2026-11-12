"""Create a SQLite backup. PostgreSQL production should use scheduled pg_dump."""
import os, sqlite3
from datetime import datetime
from pathlib import Path
base=Path(__file__).resolve().parent
if os.environ.get('DATABASE_URL','').startswith(('postgres://','postgresql://')):
    raise SystemExit('PostgreSQL detected. Schedule pg_dump for DATABASE_URL on the production host.')
src=base/'inharitense.db'
if not src.exists(): raise SystemExit('No SQLite database found.')
out=base/'backups';out.mkdir(exist_ok=True)
dst=out/f'inharitense-{datetime.now():%Y%m%d-%H%M%S}.db'
with sqlite3.connect(src) as a, sqlite3.connect(dst) as b: a.backup(b)
print(dst)
