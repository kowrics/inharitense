"""Static deployment checklist; does not require Flask to be installed."""
from pathlib import Path
import re
root=Path(__file__).resolve().parent
required=['app.py','requirements.txt','Dockerfile','docker-compose.yml','.env.example','run_production.bat','README.md']
missing=[x for x in required if not (root/x).exists()]
app=(root/'app.py').read_text()
checks={
 'debug disabled': 'debug=False' in app,
 'production secret required': "SECRET_KEY must be set in production" in app,
 'csrf enabled': 'Invalid or missing CSRF token' in app,
 'postgres support': 'psycopg' in app,
 'transaction history protection': 'cannot be deleted. Archive it instead.' in app,
 'production demo data disabled': 'not IS_PRODUCTION' in app,
}
print('Missing files:', missing or 'none')
for k,v in checks.items(): print(f'{k}:', 'PASS' if v else 'FAIL')
