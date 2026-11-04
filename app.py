from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta, date
from io import BytesIO, StringIO
from pathlib import Path
import sqlite3, os, csv, math, secrets, logging, time, re

BASE_DIR = Path(__file__).resolve().parent
# SQLITE_DB_PATH lets tests/tools point at an isolated SQLite file instead of the
# real development database. Unset in normal operation, so behavior is unchanged.
DB_PATH = Path(os.environ.get('SQLITE_DB_PATH') or (BASE_DIR / 'inharitense.db'))
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
IS_POSTGRES = DATABASE_URL.startswith(('postgres://', 'postgresql://'))
APP_ENV = os.environ.get('APP_ENV', 'development').lower()
IS_PRODUCTION = APP_ENV == 'production'

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY') or ('inharitense-dev-secret-change-me' if not IS_PRODUCTION else None),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
if IS_PRODUCTION and not app.config['SECRET_KEY']:
    raise RuntimeError('SECRET_KEY must be set in production.')

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper(), format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('inharitense')

CATEGORY_MAP={
'OE':'Office Equipment','OF':'Office Furniture and Fixtures','OS':'Office Supplies','JS':'Janitorial Supplies',
'PE':'Pantry Equipment','PF':'Pantry Furnitures and Fixtures','PS':'Pantry Supplies','EF':'Emergency Food',
'PU':'Pantry Utensils','SE':'Staff House Equipment','SF':'Staff House Furniture and Fixtures'}
CATEGORIES=list(CATEGORY_MAP.values())
CATEGORY_CODES={v:k for k,v in CATEGORY_MAP.items()}
GL_MAP={'Pantry Equipment and Furnitures':['Pantry Equipment','Pantry Furnitures and Fixtures'],
'Pantry Supplies':['Pantry Supplies','Emergency Food'],
'Office Assets':['Office Equipment','Office Furniture and Fixtures','Office Supplies'],
'Janitorial':['Janitorial Supplies'],'Pantry Other':['Pantry Utensils'],
'Staff House':['Staff House Equipment','Staff House Furniture and Fixtures']}
ROLE_LABELS={'Super User':'Super User (Legacy Admin)','Encoder':'Encoder','Report Generator':'Report Generator (Legacy)','Employee':'Employee (Legacy)','Admin':'Admin','Inventory Manager':'Inventory Manager','Requisition Officer':'Requisition Officer','Finance':'Finance'}
ROLE_CATEGORIES={r:CATEGORIES for r in ROLE_LABELS}
FORECAST_CATEGORIES={'Office Supplies','Janitorial Supplies','Pantry Supplies','Emergency Food'}
ASSET_CATEGORIES={'Office Equipment','Office Furniture and Fixtures','Pantry Equipment','Pantry Furnitures and Fixtures','Pantry Utensils','Staff House Equipment','Staff House Furniture and Fixtures'}
DEFAULT_USERS=[('System Administrator','admin@ecmci.com','Super User','Admin','admin123'),('Inventory Encoder','encoder@ecmci.com','Encoder','IT / Admin','encoder123'),('Report Generator','reports@ecmci.com','Report Generator','Admin','report123'),('ECMCI Employee','employee@ecmci.com','Employee','Operations','employee123')]
DEFAULT_INVENTORY=[
('PPE-001','ECMCI-PPE-001','Surgical Masks (box)','Office Supplies','box',42,60,18,450,'MedSure Supplies PH','Admin','Good','2026-06-02',None),('PPE-002','ECMCI-PPE-002','Nitrile Gloves (box)','Office Supplies','box',18,40,15,380,'MedSure Supplies PH','Admin','Good','2026-06-02',None),('PPE-003','ECMCI-PPE-003','Alcohol / Hand Sanitizer (500ml)','Office Supplies','bottle',26,40,10,120,'MedSure Supplies PH','Admin','Good','2026-05-10','2026-09-20'),('PPE-004','ECMCI-PPE-004','Disinfectant Wipes (pack)','Office Supplies','pack',12,30,12,95,'CleanPro Solutions','Admin','Good','2026-05-10','2027-01-15'),
('HSE-001','ECMCI-HSE-001','First Aid Kit','Office Equipment','kit',6,10,3,850,'SafeCare Equipment','Admin','Good','2026-03-18',None),('HSE-002','ECMCI-HSE-002','Digital Thermometer','Office Equipment','piece',8,12,4,350,'SafeCare Equipment','Admin','Good','2026-03-18',None),('HSE-003','ECMCI-HSE-003','Disposable Face Shield','Office Equipment','piece',14,25,8,60,'SafeCare Equipment','Admin','Good','2026-04-22',None),
('OFF-001','ECMCI-OFF-001','Bond Paper (ream)','Office Supplies','ream',58,100,25,220,'OfficeHub Philippines','Admin','Good','2026-07-01',None),('OFF-002','ECMCI-OFF-002','Printer Ink Cartridge','Office Supplies','cartridge',14,25,7,650,'OfficeHub Philippines','Admin','Good','2026-07-01',None),('OFF-003','ECMCI-OFF-003','Ballpen (box)','Office Supplies','box',9,40,12,150,'OfficeHub Philippines','Admin','Good','2026-06-15',None),
('ITB-001','ECMCI-ITB-001','Headset','Office Equipment','piece',32,45,15,1200,'TechServe BPO Systems','IT / Admin','Good','2026-02-10',None),('ITB-002','ECMCI-ITB-002','Laptop (Dell Latitude)','Office Equipment','piece',24,30,8,32000,'TechServe BPO Systems','IT / Admin','Good','2026-01-20',None),('ITB-003','ECMCI-ITB-003','LCD Monitor 24"','Office Equipment','piece',12,30,15,6500,'TechServe BPO Systems','IT / Admin','Good','2026-01-20',None),
('FAC-001','ECMCI-FAC-001','Tissue (pack)','Janitorial Supplies','pack',65,80,20,85,'CleanPro Solutions','Admin','Good','2026-07-20',None),('FAC-002','ECMCI-FAC-002','Heavy-Duty Trash Bags (roll)','Janitorial Supplies','roll',18,30,10,180,'CleanPro Solutions','Admin','Good','2026-07-20',None),('FAC-003','ECMCI-FAC-003','Surface Disinfectant (1L)','Janitorial Supplies','bottle',7,15,6,150,'CleanPro Solutions','Admin','Good','2026-06-05','2026-09-25')]
DEFAULT_VENDORS=[('MedSure Supplies PH','Office Supplies','Masks, Gloves, Sanitizer','Active'),('CleanPro Solutions','Janitorial Supplies','Wipes, Disinfectant, Tissue','Active'),('OfficeHub Philippines','Office Supplies','Paper, Ink, Ballpen','Active'),('TechServe BPO Systems','Office Equipment','Headsets, Laptops, Monitors','Active'),('SafeCare Equipment','Office Equipment','First Aid, Thermometers','Active')]

class DBConn:
    """Small compatibility layer so the existing app can run on SQLite or PostgreSQL."""
    def __init__(self):
        self.pg = IS_POSTGRES
        if self.pg:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as e:
                raise RuntimeError('PostgreSQL support requires psycopg[binary]. Run pip install -r requirements.txt') from e
            self.c = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        else:
            self.c = sqlite3.connect(str(DB_PATH), timeout=15)
            self.c.row_factory = sqlite3.Row
            self.c.execute('PRAGMA foreign_keys=ON')
            self.c.execute('PRAGMA journal_mode=WAL')
    def _sql(self, sql): return sql.replace('?', '%s') if self.pg else sql
    def execute(self, sql, params=()): return self.c.execute(self._sql(sql), params)
    def executescript(self, script):
        if not self.pg: return self.c.executescript(script)
        for stmt in (x.strip() for x in script.split(';') if x.strip()): self.c.execute(stmt)
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self): self.c.close()

def db(): return DBConn()
def now(): return datetime.now().isoformat(timespec='seconds')
def dt_display(v):
    try:return datetime.fromisoformat(v).strftime('%b %d, %Y · %I:%M %p').replace('· 0','· ')
    except:return str(v or '')
app.jinja_env.filters['dt']=dt_display

def schema():
    idtype = 'SERIAL PRIMARY KEY' if IS_POSTGRES else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    return f'''
    CREATE TABLE IF NOT EXISTS users(id {idtype},name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,department TEXT,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,last_login TEXT);
    CREATE TABLE IF NOT EXISTS inventory(id {idtype},item_no TEXT UNIQUE NOT NULL,code TEXT UNIQUE,name TEXT NOT NULL,category TEXT NOT NULL,unit TEXT NOT NULL,qty INTEGER NOT NULL DEFAULT 0,max_qty INTEGER NOT NULL DEFAULT 1,min_qty INTEGER NOT NULL DEFAULT 0,cost REAL NOT NULL DEFAULT 0,vendor TEXT,custodian TEXT,condition TEXT DEFAULT 'Good',received_date TEXT,expiry TEXT,times_out INTEGER DEFAULT 0,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS movements(id {idtype},inventory_id INTEGER NOT NULL,movement_type TEXT NOT NULL,quantity INTEGER NOT NULL,note TEXT,by_user INTEGER,created_at TEXT NOT NULL,FOREIGN KEY(inventory_id) REFERENCES inventory(id),FOREIGN KEY(by_user) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS requests(id {idtype},request_no TEXT UNIQUE NOT NULL,inventory_id INTEGER NOT NULL,quantity INTEGER NOT NULL,purpose TEXT,requester_id INTEGER NOT NULL,status TEXT NOT NULL,purchasing_note TEXT,hr_note TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,purchasing_by INTEGER,purchasing_at TEXT,hr_by INTEGER,hr_at TEXT,FOREIGN KEY(inventory_id) REFERENCES inventory(id),FOREIGN KEY(requester_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS vendors(id {idtype},name TEXT UNIQUE NOT NULL,category TEXT,supplies TEXT,status TEXT DEFAULT 'Active',contact TEXT,email TEXT,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS audit_logs(id {idtype},user_id INTEGER,action TEXT NOT NULL,item_no TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS notifications(id {idtype},recipient_role TEXT,recipient_user INTEGER,title TEXT,message TEXT,kind TEXT,read_flag INTEGER DEFAULT 0,created_at TEXT NOT NULL,FOREIGN KEY(recipient_user) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS assignments(id {idtype},assignment_no TEXT UNIQUE NOT NULL,inventory_id INTEGER NOT NULL,employee_id INTEGER NOT NULL,quantity INTEGER NOT NULL DEFAULT 1,department TEXT,assigned_by INTEGER,assigned_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Pending Acknowledgement',acknowledged_at TEXT,signature_name TEXT,signature_data TEXT,notes TEXT,FOREIGN KEY(inventory_id) REFERENCES inventory(id),FOREIGN KEY(employee_id) REFERENCES users(id),FOREIGN KEY(assigned_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS purchase_requisitions(id {idtype},pr_no TEXT UNIQUE NOT NULL,inventory_id INTEGER,description TEXT NOT NULL,quantity INTEGER NOT NULL,justification TEXT,needed_by TEXT,status TEXT NOT NULL DEFAULT 'Prepared',prepared_by INTEGER,created_at TEXT NOT NULL,FOREIGN KEY(inventory_id) REFERENCES inventory(id),FOREIGN KEY(prepared_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS inventory_audits(id {idtype},audit_no TEXT UNIQUE NOT NULL,title TEXT NOT NULL,department TEXT,category TEXT,status TEXT NOT NULL DEFAULT 'Open',created_by INTEGER,created_at TEXT NOT NULL,finalized_at TEXT,FOREIGN KEY(created_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS inventory_audit_items(id {idtype},audit_id INTEGER NOT NULL,inventory_id INTEGER NOT NULL,expected_qty INTEGER NOT NULL,actual_qty INTEGER,status TEXT NOT NULL DEFAULT 'Unchecked',notes TEXT,FOREIGN KEY(audit_id) REFERENCES inventory_audits(id),FOREIGN KEY(inventory_id) REFERENCES inventory(id));
    CREATE TABLE IF NOT EXISTS asset_disposals(id {idtype},reference_no TEXT UNIQUE NOT NULL,inventory_id INTEGER NOT NULL,quantity INTEGER NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Pending Finance Approval',requested_by INTEGER NOT NULL,requested_at TEXT NOT NULL,decided_by INTEGER,decided_at TEXT,decision_note TEXT,FOREIGN KEY(inventory_id) REFERENCES inventory(id),FOREIGN KEY(requested_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS stock_adjustments(id {idtype},reference_no TEXT UNIQUE NOT NULL,inventory_id INTEGER NOT NULL,expected_qty INTEGER NOT NULL,proposed_qty INTEGER NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Pending Manager Approval',requested_by INTEGER NOT NULL,requested_at TEXT NOT NULL,decided_by INTEGER,decided_at TEXT,decision_note TEXT,FOREIGN KEY(inventory_id) REFERENCES inventory(id),FOREIGN KEY(requested_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS purchase_orders(id {idtype},po_no TEXT UNIQUE NOT NULL,requisition_id INTEGER NOT NULL UNIQUE,vendor_id INTEGER NOT NULL,unit_cost REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'Ordered',ordered_by INTEGER NOT NULL,ordered_at TEXT NOT NULL,received_qty INTEGER NOT NULL DEFAULT 0,notes TEXT,FOREIGN KEY(requisition_id) REFERENCES purchase_requisitions(id),FOREIGN KEY(vendor_id) REFERENCES vendors(id));
    CREATE TABLE IF NOT EXISTS purchase_receipts(id {idtype},receipt_no TEXT UNIQUE NOT NULL,purchase_order_id INTEGER NOT NULL,quantity INTEGER NOT NULL,accepted_qty INTEGER NOT NULL,rejected_qty INTEGER NOT NULL,received_by INTEGER NOT NULL,received_at TEXT NOT NULL,condition_notes TEXT,FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(id));
    CREATE TABLE IF NOT EXISTS asset_transfers(id {idtype},reference_no TEXT UNIQUE NOT NULL,inventory_id INTEGER NOT NULL,quantity INTEGER NOT NULL,from_department TEXT,to_department TEXT,from_employee INTEGER,to_employee INTEGER,kind TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Pending',requested_by INTEGER NOT NULL,requested_at TEXT NOT NULL,completed_by INTEGER,completed_at TEXT,notes TEXT,FOREIGN KEY(inventory_id) REFERENCES inventory(id));
    CREATE TABLE IF NOT EXISTS asset_maintenance(id {idtype},reference_no TEXT UNIQUE NOT NULL,inventory_id INTEGER NOT NULL,kind TEXT NOT NULL,condition_before TEXT,condition_after TEXT,description TEXT NOT NULL,cost REAL NOT NULL DEFAULT 0,performed_on TEXT NOT NULL,recorded_by INTEGER NOT NULL,recorded_at TEXT NOT NULL,FOREIGN KEY(inventory_id) REFERENCES inventory(id));
    CREATE TABLE IF NOT EXISTS category_settings(id {idtype},code TEXT UNIQUE NOT NULL,name TEXT UNIQUE NOT NULL,gl_category TEXT,active INTEGER NOT NULL DEFAULT 1);
    CREATE INDEX IF NOT EXISTS idx_movements_created ON movements(created_at); CREATE INDEX IF NOT EXISTS idx_movements_item ON movements(inventory_id); CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
    '''

def init_db():
    c=db(); c.executescript(schema())
    # v4 migration: preserve existing data while adding ECMCI's revised roles and classification fields.
    inventory_columns=[('category_code','TEXT'),('gl_category','TEXT'),('description','TEXT'),('year_acquired','INTEGER'),('useful_life_years','INTEGER'),('lifecycle_status','TEXT')]
    if IS_POSTGRES:
        for col,typ in inventory_columns:c.execute(f'ALTER TABLE inventory ADD COLUMN IF NOT EXISTS {col} {typ}')
    else:
        cols={r['name'] for r in c.execute('PRAGMA table_info(inventory)').fetchall()}
        for col,typ in inventory_columns:
            if col not in cols:c.execute(f'ALTER TABLE inventory ADD COLUMN {col} {typ}')
    # v7: drafts are distinct from finalized audit results; assignment is explicit.
    audit_columns={
        'inventory_audits':[('assigned_to','INTEGER'),('draft_saved_at','TEXT'),('draft_saved_by','INTEGER'),('draft_revision','INTEGER NOT NULL DEFAULT 0')],
        'inventory_audit_items':[('draft_qty','INTEGER'),('draft_notes','TEXT')],
        'users':[('phone','TEXT'),('auth_version','INTEGER NOT NULL DEFAULT 0')]
    }
    for table,columns in audit_columns.items():
        existing=set() if IS_POSTGRES else {r['name'] for r in c.execute(f'PRAGMA table_info({table})').fetchall()}
        for column,definition in columns:
            if IS_POSTGRES:c.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}')
            elif column not in existing:c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    prcols=set() if IS_POSTGRES else {r['name'] for r in c.execute('PRAGMA table_info(purchase_requisitions)').fetchall()}
    for name,definition in [('approved_by','INTEGER'),('approved_at','TEXT'),('approval_note','TEXT')]:
        if IS_POSTGRES:c.execute(f'ALTER TABLE purchase_requisitions ADD COLUMN IF NOT EXISTS {name} {definition}')
        elif name not in prcols:c.execute(f'ALTER TABLE purchase_requisitions ADD COLUMN {name} {definition}')
    role_map={'HR':'Super User' ,'Purchasing':'Report Generator','IT Custodian':'Encoder','Department User':'Employee'}
    for old,newrole in role_map.items():c.execute('UPDATE users SET role=? WHERE role=?',(newrole,old))

    # Development/demo migration: preserve legacy user IDs (and therefore audit/request
    # references) while aligning the bundled demo database with the credentials shown
    # on the login page. Never reset credentials automatically in production.
    if not IS_PRODUCTION:
        legacy_demo_users = [
            ('hr@ecmci.com', 'System Administrator', 'admin@ecmci.com', 'Super User', 'Admin', 'admin123'),
            ('it@ecmci.com', 'Inventory Encoder', 'encoder@ecmci.com', 'Encoder', 'IT / Admin', 'encoder123'),
            ('purchasing@ecmci.com', 'Report Generator', 'reports@ecmci.com', 'Report Generator', 'Admin', 'report123'),
            ('employee@ecmci.com', 'ECMCI Employee', 'employee@ecmci.com', 'Employee', 'Operations', 'employee123'),
        ]
        for old_email, name, new_email, role, dept, pw in legacy_demo_users:
            row = c.execute('SELECT id FROM users WHERE lower(email)=lower(?) LIMIT 1', (old_email,)).fetchone()
            if row and old_email!=new_email:
                c.execute('UPDATE users SET name=?, email=?, password_hash=?, role=?, department=?, active=1 WHERE id=?',
                          (name, new_email, generate_password_hash(pw), role, dept, row['id']))
            else:
                existing = c.execute('SELECT id FROM users WHERE lower(email)=lower(?) LIMIT 1', (new_email,)).fetchone()
                if existing:
                    pass  # Preserve edited names/passwords on every subsequent startup.
                else:
                    c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
                              (name,new_email,generate_password_hash(pw),role,dept,now()))
    old_categories={'PPE & Infection Control':'Office Supplies','Health & Safety':'Office Equipment','Office Operations':'Office Supplies','IT & BPO Equipment':'Office Equipment','Facility & Sanitation':'Janitorial Supplies'}
    for oldcat,newcat in old_categories.items():c.execute('UPDATE inventory SET category=? WHERE category=?',(newcat,oldcat))
    for code,name in CATEGORY_MAP.items():
        gl=next((g for g,subs in GL_MAP.items() if name in subs),'Other')
        c.execute('INSERT INTO category_settings(code,name,gl_category) VALUES(?,?,?) ON CONFLICT DO NOTHING',(code,name,gl))
    # Keep ECMCI classification fields in sync for existing records.
    for code,name in CATEGORY_MAP.items():
        gl=next((g for g,subs in GL_MAP.items() if name in subs),'Other')
        c.execute('UPDATE inventory SET category_code=COALESCE(category_code,?), gl_category=COALESCE(gl_category,?), description=COALESCE(description,name), year_acquired=COALESCE(year_acquired,CAST(substr(received_date,1,4) AS INTEGER)) WHERE category=?',(code,gl,name))
    c.commit()
    count=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
    bootstrap_email=os.environ.get('BOOTSTRAP_ADMIN_EMAIL','').strip().lower(); bootstrap_pw=os.environ.get('BOOTSTRAP_ADMIN_PASSWORD',''); bootstrap_name=os.environ.get('BOOTSTRAP_ADMIN_NAME','System Administrator').strip()
    if count==0:
        if IS_PRODUCTION:
            if not bootstrap_email or not bootstrap_pw: raise RuntimeError('Production database is empty. Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD for the first Super User account.')
            users=[(bootstrap_name,bootstrap_email,'Super User','All',bootstrap_pw)]
        else: users=DEFAULT_USERS
        for name,email,role,dept,pw in users:c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',(name,email,generate_password_hash(pw),role,dept,now()))
    if c.execute('SELECT COUNT(*) n FROM inventory').fetchone()['n']==0 and not IS_PRODUCTION:
        for r in DEFAULT_INVENTORY:c.execute('INSERT INTO inventory(item_no,code,name,category,unit,qty,max_qty,min_qty,cost,vendor,custodian,condition,received_date,expiry,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*r,now()))
    if c.execute('SELECT COUNT(*) n FROM vendors').fetchone()['n']==0 and not IS_PRODUCTION:
        for r in DEFAULT_VENDORS:c.execute('INSERT INTO vendors(name,category,supplies,status,updated_at) VALUES(?,?,?,?,?)',(*r,now()))
    for code,name in CATEGORY_MAP.items():
        gl=next((g for g,subs in GL_MAP.items() if name in subs),'Other')
        c.execute('UPDATE inventory SET category_code=COALESCE(category_code,?), gl_category=COALESCE(gl_category,?), description=COALESCE(description,name), year_acquired=COALESCE(year_acquired,CAST(substr(received_date,1,4) AS INTEGER)) WHERE category=?',(code,gl,name))
    if c.execute('SELECT COUNT(*) n FROM movements').fetchone()['n']==0 and not IS_PRODUCTION:
        uid=c.execute("SELECT id FROM users WHERE role='Super User' LIMIT 1").fetchone()['id'];items=c.execute('SELECT id FROM inventory ORDER BY id').fetchall();seed=[(0,'in',8),(0,'out',3),(1,'out',4),(2,'out',2),(3,'in',5),(3,'out',3),(4,'out',1),(7,'out',7),(8,'out',3),(9,'out',4),(10,'out',2),(11,'out',2),(12,'out',1),(13,'in',6),(14,'out',4),(15,'out',2),(0,'out',4),(1,'in',10),(7,'out',5),(10,'out',1)]
        for idx,(item_idx,typ,q) in enumerate(seed):
            d=datetime.now()-timedelta(days=6-(idx%7),hours=(idx*3)%12); item=items[item_idx%len(items)];c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(item['id'],typ,q,'Demo historical transaction',uid,d.isoformat(timespec='seconds')))
    c.commit();c.close()

# ---- Security ----
def csrf_token():
    if not session.get('_csrf'): session['_csrf']=secrets.token_urlsafe(32)
    return session['_csrf']
app.jinja_env.globals['csrf_token']=csrf_token

# Backend policy: direct URLs and APIs receive the same authorization as navigation.
ALL_ROLES=tuple(ROLE_LABELS)
ENDPOINT_ROLES={
    'dashboard':ALL_ROLES,'api_dashboard':ALL_ROLES,'account_settings':ALL_ROLES,
    'notifications_api':ALL_ROLES,'notifications_read':ALL_ROLES,
    'inventory_page':('Super User','Encoder','Admin','Inventory Manager'), 'api_next_code':('Super User','Admin','Inventory Manager','Encoder'),
    'api_inventory_save':('Super User','Admin','Inventory Manager','Encoder'), 'api_movement':('Super User','Admin','Inventory Manager','Encoder'),
    'api_inventory_delete':('Super User','Admin'), 'api_scan':('Super User','Admin','Inventory Manager','Encoder'),
    'forecast_page':('Super User','Admin','Inventory Manager','Encoder','Report Generator'),'forecast_api':('Super User','Admin','Inventory Manager','Encoder','Report Generator'),
    'forecast_demo_api':('Super User','Admin','Inventory Manager','Encoder','Report Generator'),
    'users_page':('Super User','Admin'),'user_create':('Super User','Admin'),'user_toggle':('Super User','Admin'),
    'vendors_page':('Super User','Admin','Requisition Officer'),'vendor_save':('Super User','Admin','Requisition Officer'),'vendor_update':('Super User','Admin','Requisition Officer'),'vendor_delete':('Super User','Admin','Requisition Officer'),
    'lifecycle_page':('Super User','Admin'),'lifecycle_update':('Super User','Admin'),
    'requests_page':('Super User','Admin','Inventory Manager','Encoder','Employee'),'request_create':('Super User','Admin','Employee'),'request_action':('Super User','Admin','Inventory Manager','Encoder'),
    'assignments_page':('Super User','Admin','Inventory Manager','Encoder','Employee'),'assignment_create':('Super User','Admin','Inventory Manager','Encoder'),'assignment_ack':('Employee','Super User','Admin'),
    'requisitions_page':('Super User','Admin','Inventory Manager','Encoder','Requisition Officer'),'requisition_create':('Super User','Admin','Inventory Manager','Encoder','Requisition Officer'),'requisition_print':('Super User','Admin','Inventory Manager','Encoder','Requisition Officer'),
    'reports_v4':('Super User','Admin','Inventory Manager','Report Generator','Finance'),'reports_v4_export':('Super User','Admin','Inventory Manager','Report Generator','Finance'),
    'report':('Super User','Admin','Inventory Manager','Report Generator','Finance'),'report_xlsx':('Super User','Admin','Inventory Manager','Report Generator','Finance'),'movements_print':('Super User','Admin','Inventory Manager','Report Generator','Finance'),
    'inventory_audit_page':('Super User','Admin','Inventory Manager','Encoder'),'inventory_audit_detail':('Super User','Admin','Inventory Manager','Encoder'),
    'inventory_audit_create':('Super User','Admin','Inventory Manager'),'inventory_audit_assign':('Super User','Admin','Inventory Manager'),
    'asset_controls_page':('Super User','Admin','Inventory Manager','Encoder','Finance'),
    'disposal_request':('Super User','Admin','Inventory Manager','Encoder'),
    'disposal_decision':('Super User','Admin','Finance'),
    'adjustment_request':('Super User','Admin','Encoder'),
    'adjustment_decision':('Super User','Admin','Inventory Manager'),
    'procurement_page':('Super User','Admin','Inventory Manager','Requisition Officer','Encoder','Finance'),
    'procurement_pr_decision':('Super User','Admin','Inventory Manager'),
    'procurement_create_order':('Super User','Admin','Requisition Officer'),
    'procurement_receive':('Super User','Admin','Inventory Manager','Encoder'),
    'asset_operations_page':('Super User','Admin','Inventory Manager','Encoder','Finance'),
    'asset_transfer_create':('Super User','Admin','Inventory Manager','Encoder'),
    'asset_transfer_complete':('Super User','Admin','Inventory Manager'),
    'asset_maintenance_create':('Super User','Admin','Inventory Manager','Encoder'),
    'client_reports':('Super User','Admin','Inventory Manager','Requisition Officer','Finance','Report Generator'),
    'client_reports_export':('Super User','Admin','Inventory Manager','Requisition Officer','Finance','Report Generator')
}
@app.before_request
def enforce_endpoint_role():
    permitted=ENDPOINT_ROLES.get(request.endpoint)
    if permitted is None:return
    u=current_user()
    if not u:return redirect(url_for('login'))
    if u['role'] not in permitted:abort(403)

@app.before_request
def protect_request():
    if request.method in ('POST','PUT','PATCH','DELETE'):
        if request.endpoint == 'login': return
        supplied=request.headers.get('X-CSRFToken') or request.form.get('_csrf')
        if not supplied or not secrets.compare_digest(supplied, session.get('_csrf','')):
            abort(400, description='Invalid or missing CSRF token.')
    if request.path.startswith('/api/') and request.method=='GET': return

@app.after_request
def security_headers(resp):
    resp.headers['X-Content-Type-Options']='nosniff';resp.headers['X-Frame-Options']='DENY';resp.headers['Referrer-Policy']='strict-origin-when-cross-origin';resp.headers['Permissions-Policy']='camera=(self), microphone=()';resp.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    if IS_PRODUCTION: resp.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return resp

LOGIN_ATTEMPTS={}
def login_allowed(ip):
    data=LOGIN_ATTEMPTS.get(ip); return not data or data['until']<=time.time()
def record_login_failure(ip):
    d=LOGIN_ATTEMPTS.setdefault(ip,{'count':0,'until':0});d['count']+=1
    if d['count']>=5:d['until']=time.time()+300;d['count']=0

def current_user():
    uid=session.get('user_id');
    if not uid:return None
    c=db();u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(uid,)).fetchone();c.close();
    if u and session.get('auth_version',0)!=u['auth_version']:return None
    return u

def audit(action,item_no=None):
    u=current_user();c=db();c.execute('INSERT INTO audit_logs(user_id,action,item_no,created_at) VALUES(?,?,?,?)',(u['id'] if u else None,action,item_no,now()));c.commit();c.close()
def allowed(cat):
    u=current_user();return bool(u and cat in ROLE_CATEGORIES.get(u['role'],[]))
def get_item(iid):
    c=db();r=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone();c.close();return r
def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if not current_user():return redirect(url_for('login'))
        return f(*a,**k)
    return w
def roles(*allowed_roles):
    def deco(f):
        @wraps(f)
        def w(*a,**k):
            u=current_user()
            if not u:return redirect(url_for('login'))
            if u['role'] not in allowed_roles:abort(403)
            return f(*a,**k)
        return w
    return deco
def notify(role,title,message,kind='info',user_id=None,conn=None):
    # Reuses the caller's open connection when given one (conn=c), instead of opening a second
    # connection. SQLite only allows one writer at a time, so calling this mid-transaction with
    # a brand-new connection (the old behavior) deadlocked as soon as the caller had already
    # written anything uncommitted — exactly what happened on the 'fulfill' action.
    c=conn or db()
    c.execute('INSERT INTO notifications(recipient_role,recipient_user,title,message,kind,created_at) VALUES(?,?,?,?,?,?)',(role,user_id,title,message,kind,now()))
    recipients=[]
    if user_id:
        r=c.execute('SELECT email FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
        if r: recipients=[r['email']]
    elif role:
        recipients=[r['email'] for r in c.execute('SELECT email FROM users WHERE role=? AND active=1',(role,)).fetchall()]
    if not conn:
        c.commit();c.close()
    send_email(recipients,title,message)

def send_email(recipients,subject,message):
    """Optional SMTP delivery; in-app notifications always remain available."""
    if not recipients or not os.environ.get('SMTP_HOST'): return
    import smtplib
    from email.message import EmailMessage
    msg=EmailMessage();msg['Subject']=f'INHARITENSE · {subject}';msg['From']=os.environ.get('SMTP_FROM',os.environ.get('SMTP_USER',''));msg['To']=', '.join(recipients);msg.set_content(message)
    try:
        with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.environ.get('SMTP_PORT','587')),timeout=10) as server:
            if os.environ.get('SMTP_STARTTLS','1')=='1': server.starttls()
            if os.environ.get('SMTP_USER'): server.login(os.environ['SMTP_USER'],os.environ.get('SMTP_PASSWORD',''))
            server.send_message(msg)
    except Exception:
        logger.exception('SMTP notification failed; in-app notification was retained.')

def _linear_regression(xs, ys):
    """Small dependency-free ordinary least squares model for demand trend forecasting."""
    n=len(xs)
    if n<2:return 0.0,(sum(ys)/n if n else 0.0),0.0
    mx=sum(xs)/n; my=sum(ys)/n
    den=sum((x-mx)**2 for x in xs)
    slope=(sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den) if den else 0.0
    intercept=my-slope*mx
    ss_tot=sum((y-my)**2 for y in ys)
    ss_res=sum((y-(slope*x+intercept))**2 for x,y in zip(xs,ys))
    r2=(1-(ss_res/ss_tot)) if ss_tot else 0.0
    return slope,intercept,max(0.0,min(1.0,r2))

def _add_years(d, years):
    try:
        return d.replace(year=d.year+int(years))
    except ValueError:
        return d.replace(month=2,day=28,year=d.year+int(years))

def lifecycle_info(item):
    if item['category'] not in ASSET_CATEGORIES:
        return {'applicable':False,'status':'Not applicable','eol_date':None,'days_remaining':None}
    years=int(item['useful_life_years'] or 5) if 'useful_life_years' in item.keys() else 5
    try: acquired=date.fromisoformat(item['received_date']) if item['received_date'] else None
    except Exception: acquired=None
    if not acquired:
        return {'applicable':True,'status':'Missing acquisition date','eol_date':None,'days_remaining':None,'useful_life_years':years}
    eol=_add_years(acquired,years); days=(eol-date.today()).days
    condition=(item['condition'] or '').lower()
    if 'disposal' in condition: status='For Disposal'
    elif 'damaged' in condition: status='For Repair / Review'
    elif days < 0: status='Past EOL'
    elif days <= 180: status='Approaching EOL'
    else: status='Active'
    return {'applicable':True,'status':status,'eol_date':eol.isoformat(),'days_remaining':days,'useful_life_years':years}

def forecast_for(item, lead=None, safety=None):
    """
    AI/ML demand forecast for consumable inventory.

    A dependency-free Linear Regression model learns the weekly Stock OUT trend
    from up to 26 weeks of movement history. The predicted daily demand is then
    used to produce ECMCI's advisory Dynamic Reorder Point. No purchase order is
    ever created automatically.
    """
    try: lead=max(0.0,float(lead))
    except (TypeError,ValueError): lead=5.0
    try: safety=max(0.0,float(safety))
    except (TypeError,ValueError): safety=3.0

    if item['category'] not in FORECAST_CATEGORIES:
        return {'eligible':False,'model':'Not applicable','data_status':'Asset / non-consumable item','daily':0,'predicted_weekly':0,'days_to_reorder':0,'recommended':0,'lead_time':lead,'safety':safety,'reorder_point':float(item['min_qty'] or 0),'urgent':item['qty']<=item['min_qty'],'sample_weeks':0,'r2':0}

    week_end=date.today()-timedelta(days=date.today().weekday())
    start=week_end-timedelta(weeks=26)
    c=db()
    rows=c.execute("SELECT quantity,created_at FROM movements WHERE inventory_id=? AND movement_type='out' AND created_at>=? AND created_at<? ORDER BY created_at",(item['id'],start.isoformat(),week_end.isoformat())).fetchall()
    c.close()
    weekly=[]
    for w in range(26):
        ws=start+timedelta(days=w*7); we=ws+timedelta(days=7)
        total=sum(int(r['quantity'] or 0) for r in rows if ws <= _parse_dt(r['created_at']).date() < we)
        weekly.append(total)
    return _forecast_from_weekly(item, weekly, lead, safety)


def _forecast_from_weekly(item, weekly, lead, safety):
    """Shared calculation for recorded usage and explicitly labeled sample preview."""
    active_weeks=sum(1 for y in weekly if y>0)
    total_usage=sum(weekly)
    if active_weeks < 4 or total_usage <= 0:
        rp=float(item['min_qty'] or 0)
        return {'eligible':True,'model':'Linear Regression','data_status':'Insufficient historical usage','daily':0,'predicted_weekly':0,'days_to_reorder':0,'recommended':0,'lead_time':lead,'safety':safety,'reorder_point':round(rp,1),'urgent':item['qty']<=rp,'sample_weeks':26,'active_weeks':active_weeks,'r2':0,'history_weeks':weekly}

    xs=list(range(len(weekly))); slope,intercept,r2=_linear_regression(xs,weekly)
    next_week=max(0.0,slope*len(weekly)+intercept)
    # Blend learned trend with recent actual mean to avoid unstable extrapolation.
    recent=weekly[-8:]; recent_mean=sum(recent)/len(recent)
    predicted_weekly=max(0.0,(next_week*0.65)+(recent_mean*0.35))
    daily=predicted_weekly/7.0
    reorder_point=(daily*lead)+safety
    days_to_reorder=max(0.0,(item['qty']-reorder_point)/daily) if daily>0 else 999.0
    urgent=item['qty']<=reorder_point
    target=max(float(item['max_qty'] or 0), reorder_point+predicted_weekly)
    recommended=max(1,math.ceil(target-item['qty'])) if urgent else 0
    return {'eligible':True,'model':'Linear Regression','data_status':'Sufficient data','daily':round(daily,2),'predicted_weekly':round(predicted_weekly,2),'days_to_reorder':round(days_to_reorder,1),'recommended':recommended,'lead_time':round(lead,1),'safety':round(safety,1),'reorder_point':round(reorder_point,1),'urgent':urgent,'sample_weeks':26,'active_weeks':active_weeks,'r2':round(r2,3),'trend_per_week':round(slope,2),'history_weeks':weekly}


def _parse_dt(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return datetime.min

def dashboard_payload():
    u=current_user()
    if u['role']=='Employee':
        c=db();assigned=c.execute('SELECT i.*,a.quantity assigned_qty FROM assignments a JOIN inventory i ON i.id=a.inventory_id WHERE a.employee_id=?',(u['id'],)).fetchall()
        count=c.execute("SELECT COUNT(*) n FROM requests WHERE requester_id=? AND status NOT IN ('Fulfilled','Rejected by Encoder','Rejected by Super User')",(u['id'],)).fetchone()['n']
        unread=c.execute('SELECT COUNT(*) n FROM notifications WHERE read_flag=0 AND recipient_user=?',(u['id'],)).fetchone()['n'];c.close()
        category_levels=[dict(category=cat,qty=sum(x['assigned_qty'] for x in assigned if x['category']==cat),min=0,items=sum(1 for x in assigned if x['category']==cat)) for cat in sorted({x['category'] for x in assigned})]
        return dict(total_items=len(assigned),categories=len(category_levels),low=0,out=0,expiring=0,pending=count,pending_all=count,value=0,movements=[dict(label=(date.today()-timedelta(days=n)).strftime('%b %d'),**{'in':0,'out':0,'count':0}) for n in range(6,-1,-1)],category_levels=category_levels,health=dict(healthy=len(assigned),reorder=0,out=0),recent=[],unread=unread)
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();inv=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();value=sum(x['qty']*x['cost'] for x in inv);low=[x for x in inv if x['qty']<=x['min_qty'] and x['qty']>0];out=[x for x in inv if x['qty']==0];exp=[x for x in inv if x['expiry'] and x['expiry']<= (date.today()+timedelta(days=30)).isoformat()]
    pending=c.execute("SELECT COUNT(*) n FROM requests WHERE requester_id=? AND status NOT IN ('Fulfilled','Rejected by Encoder','Rejected by Super User')",(u['id'],)).fetchone()['n']
    recent=c.execute(f'SELECT m.*,i.name,i.item_no,i.unit,u.name by_name FROM movements m JOIN inventory i ON i.id=m.inventory_id LEFT JOIN users u ON u.id=m.by_user WHERE i.category IN ({ph}) ORDER BY m.created_at DESC LIMIT 12',cats).fetchall();days=[]
    for n in range(6,-1,-1):
        d=date.today()-timedelta(days=n);start=d.isoformat();end=(d+timedelta(days=1)).isoformat();r=c.execute(f"SELECT COALESCE(SUM(CASE WHEN m.movement_type='in' THEN quantity ELSE 0 END),0) ins,COALESCE(SUM(CASE WHEN m.movement_type='out' THEN quantity ELSE 0 END),0) outs,COUNT(*) cnt FROM movements m JOIN inventory i ON i.id=m.inventory_id WHERE i.category IN ({ph}) AND m.created_at>=? AND m.created_at<?",(*cats,start,end)).fetchone();days.append({'label':d.strftime('%b %d'),'in':r['ins'],'out':r['outs'],'count':r['cnt']})
    bycat=[]
    for cat in cats:
        r=c.execute('SELECT COALESCE(SUM(qty),0) qty,COALESCE(SUM(min_qty),0) min_qty,COUNT(*) items FROM inventory WHERE category=?',(cat,)).fetchone();bycat.append({'category':cat,'qty':r['qty'],'min':r['min_qty'],'items':r['items']})
    health={'healthy':sum(1 for x in inv if x['qty']>x['min_qty']),'reorder':sum(1 for x in inv if 0<x['qty']<=x['min_qty']),'out':len(out)};requests_count=c.execute("SELECT COUNT(*) n FROM requests WHERE status IN ('For Review','For Super User Approval','Approved')").fetchone()['n'];unread=c.execute("SELECT COUNT(*) n FROM notifications WHERE read_flag=0 AND (recipient_role=? OR recipient_user=?)",(u['role'],u['id'])).fetchone()['n'];c.close();return {'total_items':len(inv),'categories':len(cats),'low':len(low),'out':len(out),'expiring':len(exp),'pending':pending,'pending_all':requests_count,'value':round(value,2),'movements':days,'category_levels':bycat,'health':health,'recent':[dict(x) for x in recent],'unread':unread}

@app.context_processor
def inject():
    u=current_user()
    cats=ROLE_CATEGORIES[u['role']] if u else CATEGORIES
    counts={}
    if u:
        c=db();rows=c.execute('SELECT category, COUNT(*) n FROM inventory GROUP BY category').fetchall();c.close()
        counts={r['category']:r['n'] for r in rows}
        if u['role'] in ('Employee','Finance','Requisition Officer'):cats=[];counts={}
    return {'me':u,'role_labels':ROLE_LABELS,'categories':cats,'category_counts':counts}

@app.route('/healthz')
def healthz():
    """Liveness/readiness probe for Docker/orchestrators. Unauthenticated on purpose (it's
    infrastructure plumbing, not app data) and touches the database so a broken PostgreSQL
    connection makes the container report unhealthy instead of silently looking fine."""
    try:
        c=db();c.execute('SELECT 1');c.close();return jsonify(status='ok'),200
    except Exception:
        logger.exception('Health check failed: database unreachable')
        return jsonify(status='error',detail='database unreachable'),503

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user():return redirect(url_for('dashboard'))
    if request.method=='POST':
        ip=request.remote_addr or 'unknown'
        if not login_allowed(ip):flash('Too many failed attempts. Try again in 5 minutes.','error');return render_template('login.html'),429
        email=request.form.get('email','').strip().lower();pw=request.form.get('password','');c=db();u=c.execute('SELECT * FROM users WHERE lower(email)=? AND active=1',(email,)).fetchone()
        if not u or not check_password_hash(u['password_hash'],pw):c.close();record_login_failure(ip);flash('Invalid email or password.','error')
        else:
            LOGIN_ATTEMPTS.pop(ip,None);c.execute('UPDATE users SET last_login=? WHERE id=?',(now(),u['id']));c.commit();c.close();session.clear();session['user_id']=u['id'];session['auth_version']=u['auth_version'];session.permanent=True;csrf_token();audit('Signed in to the inventory system');return redirect(url_for('dashboard'))
    return render_template('login.html')
@app.route('/settings',methods=['GET','POST'])
@login_required
def account_settings():
    u=current_user();errors=[];values=dict(u)
    if request.method=='POST':
        name=(request.form.get('name') or '').strip();email=(request.form.get('email') or '').strip().lower();phone=(request.form.get('phone') or '').strip()
        current=request.form.get('current_password','');new=request.form.get('new_password','');confirm=request.form.get('confirm_password','')
        values.update(name=name,email=email,phone=phone)
        if not 2<=len(name)<=100:errors.append('Your name must contain 2–100 characters.')
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):errors.append('Enter a valid email address.')
        if len(phone)>40:errors.append('Contact number must be 40 characters or fewer.')
        changing_password=bool(new or confirm)
        if (changing_password or email!=u['email'].lower()) and not check_password_hash(u['password_hash'],current):errors.append('Your current password is incorrect.')
        if changing_password:
            if len(new)<10 or len(new)>128 or not re.search(r'[A-Za-z]',new) or not re.search(r'[0-9]',new):errors.append('Use 10–128 characters with at least one letter and one number.')
            if new!=confirm:errors.append('New passwords do not match.')
        c=db();duplicate=c.execute('SELECT id FROM users WHERE lower(email)=lower(?) AND id<>?',(email,u['id'])).fetchone()
        if duplicate:errors.append('That email address is already in use.')
        if not errors:
            try:
                version=u['auth_version']+(1 if changing_password else 0)
                password=generate_password_hash(new) if changing_password else u['password_hash']
                c.execute('UPDATE users SET name=?,email=?,phone=?,password_hash=?,auth_version=? WHERE id=?',(name,email,phone,password,version,u['id']));c.commit();c.close()
                if changing_password:
                    session.clear();session['user_id']=u['id'];session['auth_version']=version;session.permanent=True;csrf_token()
                audit('Updated own account settings'+(' and changed password' if changing_password else ''))
                flash('Account updated.'+(' Your other sessions will need to sign in again.' if changing_password else ''),'success');return redirect(url_for('account_settings'))
            except Exception:
                c.rollback();c.close();logger.exception('Account update failed');errors.append('Your account could not be updated. Please try again.')
        else:c.close()
    return render_template('settings.html',values=values,errors=errors),400 if errors else 200

@app.route('/logout')
def logout():
    if current_user():audit('Signed out of the inventory system')
    session.clear();return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():return render_template('dashboard.html',data=dashboard_payload())
@app.route('/inventory')
@login_required
def inventory_page():
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();items=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();vendors=c.execute("SELECT name FROM vendors WHERE status='Active' ORDER BY name").fetchall();c.close()
    selected_category=request.args.get('category','')
    if selected_category not in cats:selected_category=''
    return render_template('inventory.html',items=[dict(x) for x in items],vendors=vendors,can_edit=u['role'] in ('Super User','Admin','Inventory Manager','Encoder'),selected_category=selected_category)

CATEGORY_PREFIX=CATEGORY_CODES
@app.route('/api/inventory/next-code')
@login_required
def api_next_code():
    """Suggests the next item number for a category (e.g. PPE-005), matching the existing
    ECMCI tagging convention, so authorized encoders do not have to invent one by hand. The server remains authoritative —
    this is a suggestion, not a lock."""
    cat=(request.args.get('category') or '').strip()
    prefix=CATEGORY_PREFIX.get(cat)
    if not prefix or not allowed(cat):return jsonify(error='Unknown or unauthorized category.'),400
    name=(request.args.get('name') or 'Item').strip(); acquired=request.args.get('acquired') or date.today().isoformat()
    item_no=next_tag(cat,name,acquired)
    return jsonify(item_no=item_no,code=item_no)
@app.route('/api/inventory',methods=['POST'])
@login_required
def api_inventory_save():
    u=current_user();data=request.get_json(silent=True) or request.form;iid=data.get('id');cat=(data.get('category') or '').strip()
    if u['role'] not in ('Super User','Admin','Inventory Manager','Encoder') or not allowed(cat):return jsonify(error='You do not have permission for this category.'),403
    try:qty=int(data.get('qty',0));maxq=int(data.get('max_qty',1));minq=int(data.get('min_qty',0));cost=float(data.get('cost',0) or 0)
    except:return jsonify(error='Invalid numeric values.'),400
    if qty<0 or minq<0 or maxq<1 or minq>maxq or cost<0 or not math.isfinite(cost):return jsonify(error='Use nonnegative stock/cost and a maximum greater than or equal to the minimum.'),400
    name=(data.get('name') or '').strip(); acquired=(data.get('received_date') or date.today().isoformat())
    item_no=(data.get('item_no') or '').strip(); code=(data.get('code') or '').strip() or None
    if not name:return jsonify(error='Item name is required.'),400
    try:
        date.fromisoformat(acquired)
        if data.get('expiry'):date.fromisoformat(data['expiry'])
    except (ValueError,TypeError):return jsonify(error='Use valid acquisition and expiry dates.'),400
    if not iid:
        # New inventory records follow ECMCI's Category-Description-Year-Number Series tagging pattern.
        item_no=next_tag(cat,name,acquired); code=item_no
    if not item_no:return jsonify(error='Inventory tag is required.'),400
    c=db();dup=c.execute('SELECT id FROM inventory WHERE (lower(item_no)=lower(?) OR lower(name)=lower(?) OR (code IS NOT NULL AND lower(code)=lower(?))) AND id<>COALESCE(?,0)',(item_no,name,code,iid or 0)).fetchone()
    if dup:c.close();return jsonify(error='Duplicate item number, name, or code.'),409
    cat_code=CATEGORY_CODES.get(cat); gl=next((g for g,subs in GL_MAP.items() if cat in subs),'Other'); year=int(str(acquired)[:4]) if str(acquired)[:4].isdigit() else date.today().year
    vals=(item_no,code,name,cat,data.get('unit') or 'piece',qty,maxq,minq,cost,data.get('vendor') or '',data.get('custodian') or '',data.get('condition') or 'Good',acquired,data.get('expiry') or None,now())
    if iid:
        old=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
        if not old:c.close();return jsonify(error='Item not found.'),404
        if qty!=old['qty']:c.close();return jsonify(error='Use Stock IN / OUT to change quantity so transaction history stays accurate.'),409
        c.execute('UPDATE inventory SET item_no=?,code=?,name=?,category=?,unit=?,max_qty=?,min_qty=?,cost=?,vendor=?,custodian=?,condition=?,received_date=?,expiry=?,updated_at=?,category_code=?,gl_category=?,description=?,year_acquired=? WHERE id=?',(*vals[:5],*vals[6:],cat_code,gl,name,year,iid));action='Updated inventory item'
    else:
        c.execute('INSERT INTO inventory(item_no,code,name,category,unit,qty,max_qty,min_qty,cost,vendor,custodian,condition,received_date,expiry,updated_at,category_code,gl_category,description,year_acquired) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*vals,cat_code,gl,name,year));action='Created inventory item';iid=c.execute('SELECT id FROM inventory WHERE item_no=?',(item_no,)).fetchone()['id']
    if not data.get('id') and qty:
        c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(iid,'in',qty,'Opening stock',u['id'],now()))
    life_years=data.get('useful_life_years')
    try: life_years=max(1,min(30,int(life_years))) if life_years not in (None,'') else None
    except Exception: life_years=None
    life_status=(data.get('lifecycle_status') or '').strip() or None
    c.execute('UPDATE inventory SET useful_life_years=COALESCE(?,useful_life_years), lifecycle_status=COALESCE(?,lifecycle_status) WHERE id=?',(life_years,life_status,iid))
    c.commit();c.close();audit(f'{action}: {name}',item_no);return jsonify(ok=True,id=iid,message='Inventory saved.')
@app.route('/api/inventory/<int:iid>',methods=['DELETE'])
@login_required
def api_inventory_delete(iid):
    u=current_user();item=get_item(iid)
    if not item or u['role'] not in ('Super User','Admin') or not allowed(item['category']):return jsonify(error='Not allowed.'),403
    c=db();has_moves=c.execute('SELECT 1 FROM movements WHERE inventory_id=? LIMIT 1',(iid,)).fetchone();has_req=c.execute('SELECT 1 FROM requests WHERE inventory_id=? LIMIT 1',(iid,)).fetchone()
    has_links=c.execute('SELECT 1 FROM assignments WHERE inventory_id=? UNION ALL SELECT 1 FROM inventory_audit_items WHERE inventory_id=? UNION ALL SELECT 1 FROM purchase_requisitions WHERE inventory_id=?',(iid,iid,iid)).fetchone()
    if has_moves or has_req or has_links:c.close();return jsonify(error='This item has transaction history and cannot be deleted. Archive it instead.'),409
    c.execute('DELETE FROM inventory WHERE id=?',(iid,));c.commit();c.close();audit(f'Deleted inventory item: {item["name"]}',item['item_no']);return jsonify(ok=True)
@app.route('/api/movement',methods=['POST'])
@login_required
def api_movement():
    u=current_user();data=request.get_json(silent=True) or request.form
    try:iid=int(data.get('inventory_id'));qty=int(data.get('quantity',1))
    except:return jsonify(error='Invalid item or quantity.'),400
    if qty<=0:return jsonify(error='Quantity must be a positive whole number.'),400
    typ=data.get('movement_type');item=get_item(iid)
    if typ not in ('in','out') or not item or u['role'] not in ('Super User','Admin','Inventory Manager','Encoder') or not allowed(item['category']):return jsonify(error='Movement not permitted.'),403
    c=db();stamp=now()
    # The WHERE qty>=? guard makes this update atomic at the database level: the row is only
    # updated if there is still enough stock at the moment of the write, so two concurrent
    # 'out' requests can't both succeed and drive qty negative (the earlier item['qty'] read
    # above is just for a fast, friendly error message and is not relied on for correctness).
    if typ=='out':
        res=c.execute('UPDATE inventory SET qty=qty-?,times_out=times_out+?,updated_at=? WHERE id=? AND qty>=?',(qty,qty,stamp,iid,qty))
    else:
        res=c.execute('UPDATE inventory SET qty=qty+?,updated_at=? WHERE id=?',(qty,stamp,iid))
    if typ=='out' and res.rowcount==0:
        c.rollback();c.close();return jsonify(error=f'Only {item["qty"]} {item["unit"]} available.'),409
    c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(iid,typ,qty,(data.get('note') or '').strip(),u['id'],stamp))
    c.commit();newq=c.execute('SELECT qty FROM inventory WHERE id=?',(iid,)).fetchone()['qty'];c.close();audit(f'Stock {typ.upper()}: {item["name"]} x{qty}',item['item_no']);return jsonify(ok=True,qty=newq,message=f'Stock {typ.upper()} recorded.')

@app.route('/requests')
@login_required
def requests_page():
    u=current_user();c=db();
    if u['role'] in ('Super User','Encoder'):rows=c.execute('SELECT r.*,i.name item_name,i.item_no,i.unit,u.name requester,u.email requester_email FROM requests r JOIN inventory i ON i.id=r.inventory_id JOIN users u ON u.id=r.requester_id ORDER BY r.created_at DESC').fetchall()
    else:rows=c.execute('SELECT r.*,i.name item_name,i.item_no,i.unit,u.name requester,u.email requester_email FROM requests r JOIN inventory i ON i.id=r.inventory_id JOIN users u ON u.id=r.requester_id WHERE requester_id=? ORDER BY r.created_at DESC',(u['id'],)).fetchall()
    cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));items=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY name',cats).fetchall();c.close();return render_template('requests.html',requests=rows,items=items)
@app.route('/requests/create',methods=['POST'])
@login_required
def request_create():
    u=current_user()
    if u['role'] not in ('Super User','Employee'):abort(403)
    try:iid=int(request.form.get('inventory_id'));qty=max(1,int(request.form.get('quantity',1)))
    except:flash('Enter a valid quantity.','error');return redirect(url_for('requests_page'))
    item=get_item(iid)
    if not item or not allowed(item['category']):abort(403)
    reqno=f'REQ-{datetime.now().strftime("%Y%m%d%H%M%S")}-{secrets.token_hex(2).upper()}';c=db();c.execute('INSERT INTO requests(request_no,inventory_id,quantity,purpose,requester_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(reqno,iid,qty,(request.form.get('purpose') or '').strip(),u['id'],'For Review',now(),now()));c.commit();c.close();notify('Encoder','New stock request',f'{reqno} · {item["name"]} · {qty} {item["unit"]}','request');audit(f'Submitted stock request: {item["name"]}',item['item_no']);flash(f'{reqno} sent to Encoder for inventory review.','success');return redirect(url_for('requests_page'))
@app.route('/requests/<int:rid>/action',methods=['POST'])
@login_required
def request_action(rid):
    u=current_user();action=request.form.get('action');note=(request.form.get('note') or '').strip();c=db();c.execute('UPDATE requests SET status=status WHERE id=?',(rid,));r=c.execute('SELECT r.*,i.name item_name,i.item_no,i.qty current_qty,i.unit FROM requests r JOIN inventory i ON i.id=r.inventory_id WHERE r.id=?',(rid,)).fetchone()
    if not r:c.close();abort(404)
    status=None
    if action=='endorse' and u['role'] in ('Encoder','Super User') and r['status']=='For Review':status='For Super User Approval';notify('Super User','Request ready for approval',f'{r["request_no"]} · {r["item_name"]} is ready for final approval.','approval',conn=c)
    elif action=='reject_purchasing' and u['role'] in ('Encoder','Super User') and r['status']=='For Review':status='Rejected by '+u['role'];notify('', 'Request rejected', f'{r["request_no"]} was rejected by {u["role"]}.','error',user_id=r['requester_id'],conn=c)
    elif action=='approve' and u['role']=='Super User' and r['status']=='For Super User Approval':status='Approved';notify('Encoder','Request ready for release',f'{r["request_no"]} · {r["item_name"]} is approved. Check stock and release it.','request',conn=c);notify('', 'Request approved', f'{r["request_no"]} is approved and ready for Encoder release.','success',user_id=r['requester_id'],conn=c)
    elif action=='reject_hr' and u['role']=='Super User' and r['status']=='For Super User Approval':status='Rejected by Super User';notify('', 'Request rejected', f'{r["request_no"]} was rejected by Super User.','error',user_id=r['requester_id'],conn=c)
    elif action=='fulfill' and u['role'] in ('Encoder','Super User') and r['status']=='Approved':
        stamp=now()
        # Atomic guard (see api_movement for the same pattern): only deduct if enough stock is
        # still on hand at the moment of the write, so two fulfillments can't race each other
        # into negative stock even though the request was read a moment earlier.
        stock_res=c.execute('UPDATE inventory SET qty=qty-?,times_out=times_out+?,updated_at=? WHERE id=? AND qty>=?',(r['quantity'],r['quantity'],stamp,r['inventory_id'],r['quantity']))
        if stock_res.rowcount==0:c.rollback();c.close();flash('Cannot fulfill: insufficient stock.','error');return redirect(url_for('requests_page'))
        status='Fulfilled';c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(r['inventory_id'],'out',r['quantity'],f'Fulfilled {r["request_no"]}',u['id'],stamp));notify('', 'Request fulfilled', f'{r["request_no"]} · {r["item_name"]} was fulfilled.','success',user_id=r['requester_id'],conn=c)
    elif action=='note' and u['role'] in ('Super User','Encoder'):
        col='hr_note' if u['role']=='Super User' else 'purchasing_note';c.execute(f'UPDATE requests SET {col}=?,updated_at=? WHERE id=?',(note,now(),rid));c.commit();c.close();audit(f'Updated request note: {r["request_no"]}',r['item_no']);flash('Note saved.','success');return redirect(url_for('requests_page'))
    else:c.close();abort(403)
    stamp=now()
    if status:
        if action in ('endorse','reject_purchasing'):c.execute("UPDATE requests SET status=?,purchasing_note=COALESCE(NULLIF(?,''),purchasing_note),purchasing_by=?,purchasing_at=?,updated_at=? WHERE id=?",(status,note,u['id'],stamp,stamp,rid))
        elif action in ('approve','reject_hr'):c.execute("UPDATE requests SET status=?,hr_note=COALESCE(NULLIF(?,''),hr_note),hr_by=?,hr_at=?,updated_at=? WHERE id=?",(status,note,u['id'],stamp,stamp,rid))
        else:c.execute('UPDATE requests SET status=?,updated_at=? WHERE id=?',(status,stamp,rid))
        c.commit();c.close();audit(f'{status}: {r["item_name"]}',r['item_no']);flash(f'Request {status.lower()}.','success')
    return redirect(url_for('requests_page'))

@app.route('/vendors')
@login_required
@roles('Super User','Admin','Requisition Officer')
def vendors_page():
    c=db();vendors=c.execute('SELECT * FROM vendors ORDER BY category,name').fetchall();c.close();return render_template('vendors.html',vendors=vendors)
@app.route('/vendors/save',methods=['POST'])
@login_required
@roles('Super User','Admin','Requisition Officer')
def vendor_save():
    name=(request.form.get('name') or '').strip()
    if not name:flash('Vendor name is required.','error');return redirect(url_for('vendors_page'))
    c=db()
    try:
        c.execute('INSERT INTO vendors(name,category,supplies,status,contact,email,updated_at) VALUES(?,?,?,?,?,?,?)',(name,request.form.get('category'),request.form.get('supplies'),request.form.get('status','Active'),request.form.get('contact'),request.form.get('email'),now()))
        c.commit()
        audit(f'Created vendor: {name}')
        flash('Vendor added.','success')
    except Exception:
        c.rollback()
        flash('That vendor already exists or could not be saved.','error')
    c.close()
    return redirect(url_for('vendors_page'))

@app.route('/vendors/<int:vid>/update',methods=['POST'])
@login_required
@roles('Super User','Admin','Requisition Officer')
def vendor_update(vid):
    name=(request.form.get('name') or '').strip()
    if not name:
        flash('Vendor name is required.','error')
        return redirect(url_for('vendors_page'))

    c=db()
    vendor=c.execute('SELECT * FROM vendors WHERE id=?',(vid,)).fetchone()
    if not vendor:
        c.close()
        abort(404)

    try:
        c.execute('''
            UPDATE vendors
            SET name=?, category=?, supplies=?, status=?, contact=?, email=?, updated_at=?
            WHERE id=?
        ''',(
            name,
            request.form.get('category'),
            (request.form.get('supplies') or '').strip(),
            request.form.get('status','Active'),
            (request.form.get('contact') or '').strip(),
            (request.form.get('email') or '').strip(),
            now(),
            vid
        ))
        c.commit()
        audit(f'Updated vendor: {name}')
        flash('Vendor updated.','success')
    except Exception:
        c.rollback()
        flash('That vendor name already exists or could not be updated.','error')
    c.close()
    return redirect(url_for('vendors_page'))

@app.route('/vendors/<int:vid>/delete',methods=['POST'])
@login_required
@roles('Super User','Admin','Requisition Officer')
def vendor_delete(vid):
    c=db()
    vendor=c.execute('SELECT * FROM vendors WHERE id=?',(vid,)).fetchone()
    if not vendor:
        c.close()
        abort(404)

    name=vendor['name']
    c.execute('DELETE FROM vendors WHERE id=?',(vid,))
    c.commit()
    c.close()
    audit(f'Deleted vendor: {name}')
    flash(f'Vendor "{name}" deleted.','success')
    return redirect(url_for('vendors_page'))
@app.route('/users')
@login_required
@roles('Super User','Admin')
def users_page():
    c=db();users=c.execute('SELECT * FROM users ORDER BY name').fetchall();audits=c.execute('SELECT a.*,u.name user_name,u.role FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 100').fetchall();c.close();return render_template('users.html',users=users,audits=audits)
@app.route('/users/create',methods=['POST'])
@login_required
@roles('Super User','Admin')
def user_create():
    name=(request.form.get('name') or '').strip();email=(request.form.get('email') or '').strip().lower();role=request.form.get('role');dept=request.form.get('department','')
    if role not in ROLE_LABELS or not name or not email:flash('Complete the user details.','error');return redirect(url_for('users_page'))
    c=db()
    try:c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',(name,email,generate_password_hash(os.environ.get('DEFAULT_TEMP_PASSWORD','ECMCI@Welcome1')),role,dept,now()));c.commit();audit(f'Created user: {name}');flash('User created with the configured temporary password.','success')
    except Exception:c.rollback();flash('That email already exists or could not be saved.','error')
    c.close();return redirect(url_for('users_page'))
@app.route('/users/<int:uid>/toggle',methods=['POST'])
@login_required
@roles('Super User','Admin')
def user_toggle(uid):
    if current_user()['id']==uid:flash('You cannot disable your own account.','error');return redirect(url_for('users_page'))
    c=db();c.execute('UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(uid,));c.commit();c.close();audit(f'Toggled user account: {uid}');return redirect(url_for('users_page'))

@app.route('/forecast')
@login_required
@roles('Super User','Admin','Inventory Manager','Encoder','Report Generator')
def forecast_page():
    u = current_user()
    cats = ROLE_CATEGORIES[u['role']]
    ph = ','.join('?' * len(cats))

    c = db()

    forecast_cats=[x for x in cats if x in FORECAST_CATEGORIES]
    ph2=','.join('?'*len(forecast_cats))
    items = c.execute(f"SELECT * FROM inventory WHERE category IN ({ph2}) ORDER BY category,name", forecast_cats).fetchall() if forecast_cats else []

    c.close()

    return render_template(
        'forecast.html',
        items=[dict(x) for x in items],
        categories=[x for x in cats if x in FORECAST_CATEGORIES]
    )


@app.route('/api/forecast/<int:iid>')
@login_required
@roles('Super User','Admin','Inventory Manager','Encoder','Report Generator')
def forecast_api(iid):
    item = get_item(iid)

    if not item or not allowed(item['category']):
        abort(403)

    try:
        lead = max(
            0.0,
            float(request.args.get('lead', 5))
        )
    except (TypeError, ValueError):
        lead = 5.0

    try:
        safety = max(
            0.0,
            float(request.args.get('safety', 3))
        )
    except (TypeError, ValueError):
        safety = 3.0

    # Build a complete 30-day history so dates with no movement
    # still appear on the chart as zero.
    start_date = date.today() - timedelta(days=29)
    cutoff = start_date.isoformat()

    c = db()

    rows = c.execute(
        """
        SELECT
            SUBSTR(created_at, 1, 10) AS d,
            SUM(
                CASE
                    WHEN movement_type = 'out'
                    THEN quantity
                    ELSE 0
                END
            ) AS outs,
            SUM(
                CASE
                    WHEN movement_type = 'in'
                    THEN quantity
                    ELSE 0
                END
            ) AS ins
        FROM movements
        WHERE inventory_id = ?
          AND created_at >= ?
        GROUP BY SUBSTR(created_at, 1, 10)
        ORDER BY d
        """,
        (iid, cutoff)
    ).fetchall()

    c.close()

    movement_by_day = {
        r['d']: {
            'ins': int(r['ins'] or 0),
            'outs': int(r['outs'] or 0)
        }
        for r in rows
    }

    history = []

    for offset in range(30):
        d = start_date + timedelta(days=offset)
        key = d.isoformat()

        movement = movement_by_day.get(
            key,
            {
                'ins': 0,
                'outs': 0
            }
        )

        history.append({
            'd': d.strftime('%b %d'),
            'date': key,
            'ins': movement['ins'],
            'outs': movement['outs']
        })

    forecast = forecast_for(
        item,
        lead=lead,
        safety=safety
    )

    return jsonify({
        'item': dict(item),
        'forecast': forecast,
        'history': history
    })


@app.route('/api/forecast-demo/<int:iid>')
@login_required
@roles('Super User','Admin','Inventory Manager','Encoder','Report Generator')
def forecast_demo_api(iid):
    item=get_item(iid)
    if not item or not allowed(item['category']):abort(403)
    if item['category'] not in FORECAST_CATEGORIES:abort(400,description='Choose a consumable item for the sample preview.')
    try:
        lead=float(request.args.get('lead',5));safety=float(request.args.get('safety',3))
        if not math.isfinite(lead) or not math.isfinite(safety) or lead<0 or safety<0:raise ValueError()
    except (TypeError,ValueError):abort(400,description='Use finite, non-negative delivery time and safety stock.')
    # Fixed illustrative data only; never inserted into movements or inventory.
    weekly=[6,7,6,7,8,7,8,9,8,9,10,9,10,11,10,11,12,11,12,13,12,13,14,13,14,15]
    sample_item=dict(item);sample_item.update(qty=9,min_qty=5,max_qty=40)
    forecast=_forecast_from_weekly(sample_item,weekly,lead,safety)
    return jsonify(item=sample_item,forecast=forecast,history=[],is_demo=True,
                   data_source='Sample data — demonstration only',
                   disclaimer='Uses illustrative weekly usage, 9 units on hand, and a 40-unit target. It is not a prediction based on this item’s actual records. No inventory, transactions, or requisitions are changed.')



@app.route('/lifecycle')
@roles('Super User','Admin')
def lifecycle_page():
    c=db(); rows=c.execute("SELECT * FROM inventory ORDER BY category,name").fetchall(); c.close()
    assets=[]
    for r in rows:
        d=dict(r); d['life']=lifecycle_info(r)
        if d['life']['applicable']: assets.append(d)
    return render_template('lifecycle.html',items=assets)

@app.route('/lifecycle/<int:iid>/update',methods=['POST'])
@roles('Super User','Admin')
def lifecycle_update(iid):
    try: years=max(1,min(30,int(request.form.get('useful_life_years',5))))
    except Exception: years=5
    condition=(request.form.get('condition') or 'Good').strip()
    c=db(); item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
    if not item:c.close();abort(404)
    c.execute('UPDATE inventory SET useful_life_years=?,condition=?,lifecycle_status=?,updated_at=? WHERE id=?',(years,condition,lifecycle_info({**dict(item),'useful_life_years':years,'condition':condition})['status'],now(),iid));c.commit();c.close()
    audit(f'Updated EOL lifecycle settings: {item["item_no"]}',item['item_no']);flash('Lifecycle settings updated.','success');return redirect(url_for('lifecycle_page'))

@app.route('/api/notifications')
@login_required
def notifications_api():
    u=current_user();c=db();rows=c.execute('SELECT * FROM notifications WHERE (recipient_role=? OR recipient_user=?) ORDER BY created_at DESC LIMIT 30',(u['role'],u['id'])).fetchall();c.close();return jsonify([dict(r) for r in rows])
@app.route('/api/notifications/read',methods=['POST'])
@login_required
def notifications_read():
    u=current_user();c=db();c.execute('UPDATE notifications SET read_flag=1 WHERE recipient_role=? OR recipient_user=?',(u['role'],u['id']));c.commit();c.close();return jsonify(ok=True)

@app.route('/reports/<kind>')
@login_required
def report(kind):
    if kind not in ('stock','valuation','assignment','movements'):abort(404)
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();rows=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();c.close();output=StringIO();w=csv.writer(output)
    if kind=='valuation':headers=['Item No.','Item','Category','On Hand','Unit Cost (PHP)','Total Value (PHP)'];data=[[r['item_no'],r['name'],r['category'],r['qty'],r['cost'],r['qty']*r['cost']] for r in rows];fn='ECMCI_Inventory_Valuation.csv'
    elif kind=='assignment':headers=['Item No.','Item','Category','Custodian','Vendor','Condition','On Hand'];data=[[r['item_no'],r['name'],r['category'],r['custodian'],r['vendor'],r['condition'],r['qty']] for r in rows];fn='ECMCI_Asset_Assignment.csv'
    elif kind=='movements':
        c=db();m=c.execute(f'SELECT m.created_at,i.item_no,i.name,m.movement_type,m.quantity,m.note,u.name by_name FROM movements m JOIN inventory i ON i.id=m.inventory_id LEFT JOIN users u ON u.id=m.by_user WHERE i.category IN ({ph}) ORDER BY m.created_at DESC',cats).fetchall();c.close();headers=['Date','Item No.','Item','Type','Quantity','Note','Recorded By'];data=[[r['created_at'],r['item_no'],r['name'],r['movement_type'].upper(),r['quantity'],r['note'],r['by_name']] for r in m];fn='ECMCI_Stock_Movements.csv'
    else:headers=['Item No.','Item','Category','Unit','On Hand','Minimum','Maximum','Code','Vendor','Custodian','Status'];data=[[r['item_no'],r['name'],r['category'],r['unit'],r['qty'],r['min_qty'],r['max_qty'],r['code'],r['vendor'],r['custodian'],'Low stock' if r['qty']<=r['min_qty'] else 'Healthy'] for r in rows];fn='ECMCI_Current_Stock.csv'
    w.writerow(headers);w.writerows(data);return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename={fn}'})
@app.route('/reports/xlsx/<kind>')
@login_required
def report_xlsx(kind):
    if kind not in ('stock','valuation','assignment','movements'):abort(404)
    try:from openpyxl import Workbook
    except:abort(500)
    wb=Workbook();ws=wb.active
    if kind=='movements':
        ws.title='Stock Movements';ws.append(['Date','Item No.','Item','Type','Quantity','Note','Recorded By'])
        for r in movement_report_rows():ws.append([r['created_at'],r['item_no'],r['name'],r['movement_type'].upper(),r['quantity'],r['note'] or '',r['by_name'] or ''])
        filename='ECMCI_Stock_Movements.xlsx'
    else:
        u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();rows=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();c.close();ws.title='Inventory Report';ws.append(['Item No.','Item','Category','Unit','On Hand','Minimum','Maximum','Unit Cost (PHP)','Vendor','Custodian','Status'])
        for r in rows:ws.append([r['item_no'],r['name'],r['category'],r['unit'],r['qty'],r['min_qty'],r['max_qty'],r['cost'],r['vendor'],r['custodian'],'Low stock' if r['qty']<=r['min_qty'] else 'Healthy'])
        filename='ECMCI_Inventory_Report.xlsx'
    for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(max(max(len(str(x.value or '')) for x in col)+2,12),34)
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    buf=BytesIO();wb.save(buf);buf.seek(0);return send_file(buf,as_attachment=True,download_name=filename,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
@app.route('/api/dashboard')
@login_required
def api_dashboard():return jsonify(dashboard_payload())
@app.route('/api/scan')
@login_required
def api_scan():
    q=request.args.get('q','').strip().lower();c=db();item=c.execute('SELECT * FROM inventory WHERE lower(item_no)=? OR lower(code)=?',(q,q)).fetchone();c.close()
    if not item or not allowed(item['category']):return jsonify(found=False),404
    return jsonify(found=True,item=dict(item))



def next_tag(category,name,acquired):
    code=CATEGORY_CODES.get(category,'XX'); year=str(acquired or date.today().year)[:4]
    desc=''.join(ch for ch in (name or 'Item').title() if ch.isalnum())[:18] or 'Item'
    c=db(); rows=c.execute('SELECT item_no FROM inventory WHERE item_no LIKE ?',(f'{code}-{desc}-{year}-%',)).fetchall(); c.close()
    nums=[]
    for r in rows:
        try: nums.append(int(r['item_no'].split('-')[-1]))
        except: pass
    return f'{code}-{desc}-{year}-{max(nums,default=0)+1:04d}'

@app.route('/assignments')
@login_required
def assignments_page():
    u=current_user();c=db()
    if u['role']=='Employee': rows=c.execute('SELECT a.*,i.name item_name,i.item_no FROM assignments a JOIN inventory i ON i.id=a.inventory_id WHERE a.employee_id=? ORDER BY a.assigned_at DESC',(u['id'],)).fetchall()
    else: rows=c.execute('SELECT a.*,i.name item_name,i.item_no,u.name employee_name FROM assignments a JOIN inventory i ON i.id=a.inventory_id JOIN users u ON u.id=a.employee_id ORDER BY a.assigned_at DESC').fetchall()
    items=c.execute('SELECT * FROM inventory WHERE qty>0 ORDER BY name').fetchall(); employees=c.execute("SELECT * FROM users WHERE role='Employee' AND active=1 ORDER BY name").fetchall();c.close()
    return render_template('assignments.html',rows=rows,items=items,employees=employees)

@app.route('/assignments/create',methods=['POST'])
@roles('Super User','Admin','Inventory Manager','Encoder')
def assignment_create():
    try:
        iid=int(request.form['inventory_id']);eid=int(request.form['employee_id']);qty=int(request.form.get('quantity',1))
        if qty<=0:raise ValueError()
    except (KeyError,ValueError,TypeError):abort(400,description='Choose an item, an employee, and a positive whole quantity.')
    c=db();item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone();emp=c.execute("SELECT * FROM users WHERE id=? AND role='Employee' AND active=1",(eid,)).fetchone()
    if not item or not emp or not allowed(item['category']):c.close();abort(400,description='Invalid item or active employee.')
    stamp=now();u=current_user()
    result=c.execute('UPDATE inventory SET qty=qty-?,times_out=times_out+?,updated_at=? WHERE id=? AND qty>=?',(qty,qty,stamp,iid,qty))
    if result.rowcount!=1:
        c.rollback();c.close();flash('Insufficient stock. Refresh the inventory and try again.','error');return redirect(url_for('assignments_page'))
    no='ASN-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(4)
    c.execute('INSERT INTO assignments(assignment_no,inventory_id,employee_id,quantity,department,assigned_by,assigned_at,notes) VALUES(?,?,?,?,?,?,?,?)',(no,iid,eid,qty,emp['department'],u['id'],stamp,request.form.get('notes','')))
    c.execute("INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)",(iid,'out',qty,f'Assigned to {emp["name"]} · {no}',u['id'],stamp))
    c.commit();c.close();audit(f'Assigned inventory: {no}',item['item_no']);flash('Item assigned. Employee acknowledgement is now pending.','success');return redirect(url_for('assignments_page'))

@app.route('/assignments/<int:aid>/ack',methods=['POST'])
@login_required
def assignment_ack(aid):
    u=current_user();c=db();a=c.execute('SELECT * FROM assignments WHERE id=?',(aid,)).fetchone()
    if not a or a['employee_id']!=u['id'] or a['status']!='Pending Acknowledgement':c.close();abort(403)
    sig=(request.form.get('signature_name') or '').strip();
    if not sig:c.close();flash('Type your full name as your electronic signature.','error');return redirect(url_for('assignments_page'))
    c.execute("UPDATE assignments SET status='Acknowledged',acknowledged_at=?,signature_name=? WHERE id=?",(now(),sig,aid));c.commit();c.close();audit(f'Electronically acknowledged assignment {a["assignment_no"]}');flash('Receipt acknowledged and timestamped.','success');return redirect(url_for('assignments_page'))

@app.route('/requisitions')
@roles('Super User','Admin','Inventory Manager','Encoder','Requisition Officer')
def requisitions_page():
    c=db();rows=c.execute('SELECT p.*,i.item_no FROM purchase_requisitions p LEFT JOIN inventory i ON i.id=p.inventory_id ORDER BY p.created_at DESC').fetchall();items=c.execute('SELECT * FROM inventory ORDER BY name').fetchall();c.close();return render_template('requisitions.html',rows=rows,items=items)

@app.route('/requisitions/create',methods=['POST'])
@roles('Super User','Admin','Inventory Manager','Encoder','Requisition Officer')
def requisition_create():
    u=current_user();description=(request.form.get('description') or '').strip()
    try:
        qty=int(request.form.get('quantity',''));iid=int(request.form['inventory_id']) if request.form.get('inventory_id') else None
        needed=request.form.get('needed_by') or None
        if qty<=0 or not description:raise ValueError()
        if needed:date.fromisoformat(needed)
    except (TypeError,ValueError):abort(400,description='Enter a description, positive whole quantity, and a valid needed-by date.')
    c=db()
    if iid is not None:
        item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
        if not item or not allowed(item['category']):c.close();abort(400,description='Choose a valid inventory item.')
    no='PR-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(4)
    c.execute('INSERT INTO purchase_requisitions(pr_no,inventory_id,description,quantity,justification,needed_by,prepared_by,created_at,status) VALUES(?,?,?,?,?,?,?,?,?)',(no,iid,description,qty,request.form.get('justification',''),needed,u['id'],now(),'Pending Approval'))
    c.commit();c.close();audit(f'Prepared purchase requisition {no}');flash('Purchase requisition submitted for approval.','success');return redirect(url_for('requisitions_page'))


def report_filters():
    start=(request.args.get('start') or '').strip();end=(request.args.get('end') or '').strip()
    dept=(request.args.get('department') or '').strip();period=(request.args.get('period') or '').strip()
    if period not in ('','week','month'):abort(400,description='Choose a valid reporting period.')
    try:
        if start:date.fromisoformat(start)
        if end:date.fromisoformat(end)
        if start and end and start>end:raise ValueError()
    except ValueError:abort(400,description='Use a valid acquisition-date range with start before end.')
    today=date.today();pstart=pend=''
    if period=='week':pstart=(today-timedelta(days=today.weekday())).isoformat();pend=(today+timedelta(days=6-today.weekday())).isoformat()
    elif period=='month':pstart=today.replace(day=1).isoformat();pend=((today.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)).isoformat()
    return dict(start=start,end=end,department=dept,period=period,as_of=end or pend,movement_start=start or pstart,movement_end=end or pend)

def inventory_report_data():
    filters=report_filters();dept=filters['department'];active="a.status IN ('Pending Acknowledgement','Acknowledged')"
    # Legacy stock records may hold a department in custodian, before assignments existed.
    label=f"COALESCE((SELECT CASE WHEN COUNT(DISTINCT a.department)>1 THEN 'Multiple departments' ELSE MIN(a.department) END FROM assignments a WHERE a.inventory_id=i.id AND {active}),NULLIF(i.custodian,''),'Unassigned')"
    q=f"SELECT i.*, {('?' if dept else label)} assignment_department FROM inventory i WHERE 1=1";args=[dept] if dept else []
    if filters['start']:q+=' AND i.received_date>=?';args.append(filters['start'])
    if filters['end']:q+=' AND i.received_date<=?';args.append(filters['end'])
    elif filters['as_of']:q+=' AND (i.received_date<=? OR i.received_date IS NULL)';args.append(filters['as_of'])
    if dept:
        q+=f" AND (EXISTS (SELECT 1 FROM assignments a WHERE a.inventory_id=i.id AND {active} AND a.department=?) OR (NOT EXISTS (SELECT 1 FROM assignments a WHERE a.inventory_id=i.id AND {active}) AND i.custodian=?))";args.extend([dept,dept])
    c=db();rows=c.execute(q+' ORDER BY i.received_date DESC,i.name',args).fetchall()
    depts=c.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL AND department<>'' UNION SELECT DISTINCT department FROM assignments WHERE department IS NOT NULL AND department<>'' ORDER BY department").fetchall();c.close()
    return rows,depts,filters['period']

@app.route('/reports-v4')
@roles('Super User','Admin','Inventory Manager','Report Generator','Finance')
def reports_v4():
    rows,depts,period=inventory_report_data();filters=report_filters();chips=[]
    labels={'start':'Acquired from','end':'Acquired until','department':'Department','period':'Reporting period'}
    params={k:filters[k] for k in labels if filters[k]}
    for key,value in params.items():
        remaining={k:v for k,v in params.items() if k!=key}
        chips.append(dict(label=labels[key],value={'week':'This week','month':'This month'}.get(value,value),url=url_for('reports_v4',**remaining)))
    return render_template('reports_v4.html',rows=rows,depts=depts,period=period,filters=filters,filter_chips=chips)

@app.route('/reports-v4/export')
@roles('Super User','Admin','Inventory Manager','Report Generator','Finance')
def reports_v4_export():
    rows,_,_=inventory_report_data();o=StringIO();w=csv.writer(o)
    w.writerow(['Inventory Tag','Description','Category','Date Acquired','On Hand','Assigned Department / Custody'])
    for r in rows:w.writerow([r['item_no'],r['name'],r['category'],r['received_date'],r['qty'],r['assignment_department']])
    return Response(o.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=ECMCI_inventory_report.csv'})

def movement_report_rows():
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db()
    q=f"SELECT m.created_at,i.item_no,i.name,m.movement_type,m.quantity,m.note,u.name by_name FROM movements m JOIN inventory i ON i.id=m.inventory_id LEFT JOIN users u ON u.id=m.by_user WHERE i.category IN ({ph})"
    args=list(cats);filters=report_filters();start=filters['movement_start'];end=filters['movement_end']
    if start:q+=' AND date(m.created_at)>=?';args.append(start)
    if end:q+=' AND date(m.created_at)<=?';args.append(end)
    rows=c.execute(q+' ORDER BY m.created_at DESC',args).fetchall();c.close();return rows

@app.route('/reports/print/movements')
@roles('Super User','Admin','Inventory Manager','Report Generator','Finance')
def movements_print():
    return render_template('stock_movements_print.html',rows=movement_report_rows(),start=report_filters()['movement_start'],end=report_filters()['movement_end'])

@app.route('/requisitions/<int:pid>/print')
@roles('Super User','Admin','Inventory Manager','Encoder','Requisition Officer')
def requisition_print(pid):
    c=db();r=c.execute('SELECT p.*,i.item_no,u.name prepared_by_name FROM purchase_requisitions p LEFT JOIN inventory i ON i.id=p.inventory_id LEFT JOIN users u ON u.id=p.prepared_by WHERE p.id=?',(pid,)).fetchone();c.close()
    if not r:abort(404)
    return render_template('requisition_print.html',r=r)

def audit_access(record):
    u=current_user()
    return bool(record and u and (u['role'] in ('Super User','Admin','Inventory Manager') or (u['role']=='Encoder' and record['assigned_to']==u['id'])))

def audit_result(payload,status=200,aid=None):
    if 'application/json' in request.headers.get('Accept',''):return jsonify(payload),status
    if status!=200:abort(status,description=payload.get('error','Unable to save audit.'))
    flash(payload['message'],'success');return redirect(url_for('inventory_audit_detail',aid=aid))

@app.route('/inventory-audit')
@roles('Super User','Admin','Inventory Manager','Encoder')
def inventory_audit_page():
    u=current_user();c=db();q='SELECT a.*,u.name assignee_name FROM inventory_audits a LEFT JOIN users u ON u.id=a.assigned_to'
    args=()
    if u['role']=='Encoder':q+=' WHERE a.assigned_to=?';args=(u['id'],)
    audits=c.execute(q+' ORDER BY a.created_at DESC',args).fetchall()
    encoders=c.execute("SELECT id,name FROM users WHERE role='Encoder' AND active=1 ORDER BY name").fetchall();c.close()
    return render_template('inventory_audit.html',audits=audits,encoders=encoders)

@app.route('/inventory-audit/create',methods=['POST'])
@roles('Super User','Admin','Inventory Manager')
def inventory_audit_create():
    u=current_user();cat=request.form.get('category') or None;assigned=request.form.get('assigned_to') or None
    if cat and cat not in CATEGORIES:abort(400,description='Choose a valid category.')
    c=db()
    if assigned and not c.execute("SELECT id FROM users WHERE id=? AND role='Encoder' AND active=1",(assigned,)).fetchone():c.close();abort(400,description='Choose an active Encoder.')
    no='AUD-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(4)
    c.execute('INSERT INTO inventory_audits(audit_no,title,department,category,assigned_to,created_by,created_at) VALUES(?,?,?,?,?,?,?)',(no,request.form.get('title') or 'Physical Inventory Audit',request.form.get('department') or None,cat,assigned,u['id'],now()))
    aid=c.execute('SELECT id FROM inventory_audits WHERE audit_no=?',(no,)).fetchone()['id']
    items=c.execute('SELECT id,qty FROM inventory'+(' WHERE category=?' if cat else ''),((cat,) if cat else ())).fetchall()
    for x in items:c.execute('INSERT INTO inventory_audit_items(audit_id,inventory_id,expected_qty) VALUES(?,?,?)',(aid,x['id'],x['qty']))
    c.commit();c.close();audit(f'Created inventory audit {no}');return redirect(url_for('inventory_audit_detail',aid=aid))

@app.route('/inventory-audit/<int:aid>/assign',methods=['POST'])
@roles('Super User','Admin','Inventory Manager')
def inventory_audit_assign(aid):
    assigned=request.form.get('assigned_to') or None;c=db();record=c.execute('SELECT * FROM inventory_audits WHERE id=?',(aid,)).fetchone()
    if not record:c.close();abort(404)
    if record['status']=='Finalized':c.close();abort(409,description='Finalized audits cannot be reassigned.')
    if assigned and not c.execute("SELECT id FROM users WHERE id=? AND role='Encoder' AND active=1",(assigned,)).fetchone():c.close();abort(400)
    c.execute("UPDATE inventory_audits SET assigned_to=?,draft_revision=draft_revision+1 WHERE id=? AND status<>'Finalized'",(assigned,aid));c.commit();c.close()
    audit(f'Changed assignee for inventory audit {record["audit_no"]}');flash('Audit assignment updated.','success');return redirect(url_for('inventory_audit_detail',aid=aid))

@app.route('/inventory-audit/<int:aid>',methods=['GET','POST'])
@roles('Super User','Admin','Inventory Manager','Encoder')
def inventory_audit_detail(aid):
    c=db();record=c.execute('SELECT * FROM inventory_audits WHERE id=?',(aid,)).fetchone()
    if not record:c.close();abort(404)
    if not audit_access(record):c.close();abort(403)
    if request.method=='POST':
        action=request.form.get('audit_action') or ('finalize' if request.form.get('finalize') else 'draft')
        if action not in ('draft','finalize'):c.close();return audit_result({'error':'Choose save as draft or finalize.'},400)
        try:revision=int(request.form.get('draft_revision'))
        except (TypeError,ValueError):c.close();return audit_result({'error':'Invalid draft version.'},400)
        lock=c.execute("UPDATE inventory_audits SET draft_revision=draft_revision+1 WHERE id=? AND status<>'Finalized' AND draft_revision=?",(aid,revision))
        if lock.rowcount!=1:c.rollback();c.close();return audit_result({'error':'This audit was finalized or changed by another editor. Reload before saving.'},409)
        rows=c.execute('SELECT * FROM inventory_audit_items WHERE audit_id=?',(aid,)).fetchall();changes=[]
        try:
            valid_keys={f'actual_{x["id"]}' for x in rows}
            if any(k.startswith('actual_') and k not in valid_keys for k in request.form):raise ValueError('An item does not belong to this audit.')
            for x in rows:
                key=f'actual_{x["id"]}'
                raw=request.form.get(key)
                actual=x['draft_qty'] if record['draft_saved_at'] else x['actual_qty']
                if raw is not None:actual=int(raw) if raw.strip() else None
                if actual is not None and actual<0:raise ValueError('Counts must be zero or more.')
                notes=request.form.get(f'notes_{x["id"]}',x['draft_notes'] if x['draft_notes'] is not None else (x['notes'] or '')).strip()
                if action=='finalize':
                    if actual is None:raise ValueError('Count every item before finalizing.')
                    if actual!=x['expected_qty'] and not notes:raise ValueError('Explain every discrepancy before finalizing.')
                status='Unchecked' if actual is None else 'Matched' if actual==x['expected_qty'] else 'Short' if actual<x['expected_qty'] else 'Excess'
                changes.append((actual,notes,status,x['id']))
        except (ValueError,TypeError) as e:
            c.rollback();c.close();return audit_result({'error':str(e) or 'Enter valid whole-number counts.'},400)
        stamp=now()
        for actual,notes,status,xid in changes:
            c.execute('UPDATE inventory_audit_items SET draft_qty=?,draft_notes=? WHERE id=? AND audit_id=?',(actual,notes,xid,aid))
            if action=='finalize':c.execute('UPDATE inventory_audit_items SET actual_qty=?,notes=?,status=? WHERE id=? AND audit_id=?',(actual,notes,status,xid,aid))
        c.execute('UPDATE inventory_audits SET draft_saved_at=?,draft_saved_by=? WHERE id=?',(stamp,current_user()['id'],aid))
        if action=='finalize':
            c.execute("UPDATE inventory_audits SET status='Finalized',finalized_at=? WHERE id=?",(stamp,aid))
            # Final count is evidence, not permission to change stock. Every variance
            # becomes a pending, independently reviewable correction.
            for (actual,notes,status,xid), entry in zip(changes,rows):
                if actual == entry['expected_qty']:
                    continue
                inv=c.execute('SELECT item_no,qty FROM inventory WHERE id=?',(entry['inventory_id'],)).fetchone()
                if not inv:
                    c.rollback();c.close();return audit_result({'error':'An audited item no longer exists.'},409)
                ref='AUD-ADJ-'+secrets.token_hex(8)
                reason=f"Audit {record['audit_no']}, counted {actual}, expected {entry['expected_qty']}. {notes}"[:1500]
                c.execute('INSERT INTO stock_adjustments(reference_no,inventory_id,expected_qty,proposed_qty,reason,requested_by,requested_at) VALUES(?,?,?,?,?,?,?)',
                    (ref,entry['inventory_id'],inv['qty'],actual,reason,current_user()['id'],stamp))
        c.commit();c.close();audit(f'{"Finalized" if action=="finalize" else "Saved draft of"} inventory audit {record["audit_no"]}')
        return audit_result(dict(ok=True,message='Audit finalized.' if action=='finalize' else 'Draft saved. You can return and continue later.',revision=revision+1,saved_at=stamp,finalized=action=='finalize'),aid=aid)
    rows=c.execute('SELECT ai.*,i.item_no,i.name,i.category FROM inventory_audit_items ai JOIN inventory i ON i.id=ai.inventory_id WHERE ai.audit_id=? ORDER BY i.category,i.name',(aid,)).fetchall()
    encoders=c.execute("SELECT id,name FROM users WHERE role='Encoder' AND active=1 ORDER BY name").fetchall();c.close()
    return render_template('inventory_audit_detail.html',audit=record,rows=rows,encoders=encoders)


# Client process 2026: separate request/approval workflows for controlled inventory changes.
# Legacy Super User remains a privileged administrator until all old modules are migrated.
@app.route('/asset-controls')
@roles('Super User','Admin','Inventory Manager','Encoder','Finance')
def asset_controls_page():
    u=current_user();c=db()
    items=c.execute('SELECT id,item_no,name,qty FROM inventory ORDER BY name').fetchall()
    disposals=c.execute('SELECT d.*,i.item_no,i.name item_name,ru.name requester,du.name decision_maker FROM asset_disposals d JOIN inventory i ON i.id=d.inventory_id JOIN users ru ON ru.id=d.requested_by LEFT JOIN users du ON du.id=d.decided_by ORDER BY d.requested_at DESC,d.id DESC LIMIT 150').fetchall()
    adjustments=c.execute('SELECT a.*,i.item_no,i.name item_name,ru.name requester,du.name decision_maker FROM stock_adjustments a JOIN inventory i ON i.id=a.inventory_id JOIN users ru ON ru.id=a.requested_by LEFT JOIN users du ON du.id=a.decided_by ORDER BY a.requested_at DESC,a.id DESC LIMIT 150').fetchall()
    c.close();return render_template('asset_controls.html',items=items,disposals=disposals,adjustments=adjustments)

@app.route('/asset-controls/disposal/request',methods=['POST'])
@roles('Super User','Admin','Inventory Manager','Encoder')
def disposal_request():
    try:
        iid=int(request.form.get('inventory_id',''));quantity=int(request.form.get('quantity',''))
        if quantity<=0:raise ValueError()
    except (TypeError,ValueError):abort(400,description='Enter an item and positive whole quantity.')
    reason=(request.form.get('reason') or '').strip()
    if len(reason)<5:abort(400,description='Explain the proposed disposal (at least five characters).')
    c=db();item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
    if not item or item['qty']<quantity:c.close();abort(409,description='Item is missing or stock is insufficient.')
    ref='DIS-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(4)
    c.execute('INSERT INTO asset_disposals(reference_no,inventory_id,quantity,reason,requested_by,requested_at) VALUES(?,?,?,?,?,?)',(ref,iid,quantity,reason,current_user()['id'],now()))
    c.commit();c.close();audit('Requested asset disposal '+ref,item['item_no']);flash('Disposal submitted for Finance approval. Stock has not changed.','success');return redirect(url_for('asset_controls_page'))

@app.route('/asset-controls/disposal/<int:did>/decision',methods=['POST'])
@roles('Finance','Super User','Admin')
def disposal_decision(did):
    decision=request.form.get('decision');note=(request.form.get('decision_note') or '').strip()
    if decision not in ('approve','reject'):abort(400)
    if decision=='reject' and len(note)<5:abort(400,description='Provide a rejection reason.')
    c=db();row=c.execute('SELECT d.*,i.item_no FROM asset_disposals d JOIN inventory i ON i.id=d.inventory_id WHERE d.id=?',(did,)).fetchone()
    if not row:c.close();abort(404)
    if row['status']!='Pending Finance Approval':c.close();abort(409,description='This decision was already recorded.')
    # The decision and guarded stock decrement occur in the same database transaction.
    stamp=now()
    result=c.execute("UPDATE asset_disposals SET status=?,decided_by=?,decided_at=?,decision_note=? WHERE id=? AND status='Pending Finance Approval'",('Approved' if decision=='approve' else 'Rejected',current_user()['id'],stamp,note,did))
    if result.rowcount!=1:c.rollback();c.close();abort(409)
    if decision=='approve':
        result=c.execute('UPDATE inventory SET qty=qty-?,updated_at=? WHERE id=? AND qty>=?',(row['quantity'],stamp,row['inventory_id'],row['quantity']))
        if result.rowcount!=1:c.rollback();c.close();abort(409,description='Insufficient current stock; no disposal was approved.')
        c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(row['inventory_id'],'out',row['quantity'],'Approved disposal '+row['reference_no'],current_user()['id'],stamp))
    c.commit();c.close();audit('Disposal '+decision+'d '+row['reference_no'],row['item_no']);flash('Disposal decision recorded.','success');return redirect(url_for('asset_controls_page'))

@app.route('/asset-controls/adjustment/request',methods=['POST'])
@roles('Super User','Admin','Encoder')
def adjustment_request():
    try:
        iid=int(request.form.get('inventory_id',''));proposed=int(request.form.get('proposed_qty',''))
        if proposed<0:raise ValueError()
    except (TypeError,ValueError):abort(400,description='Enter a valid item and nonnegative proposed quantity.')
    reason=(request.form.get('reason') or '').strip()
    if len(reason)<5:abort(400,description='An adjustment requires a reason.')
    c=db();item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
    if not item:c.close();abort(404)
    if item['qty']==proposed:c.close();abort(400,description='New balance must differ from current balance.')
    ref='ADJ-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(4)
    c.execute('INSERT INTO stock_adjustments(reference_no,inventory_id,expected_qty,proposed_qty,reason,requested_by,requested_at) VALUES(?,?,?,?,?,?,?)',(ref,iid,item['qty'],proposed,reason,current_user()['id'],now()))
    c.commit();c.close();audit('Requested stock adjustment '+ref,item['item_no']);flash('Adjustment pending Inventory Manager approval; stock unchanged.','success');return redirect(url_for('asset_controls_page'))

@app.route('/asset-controls/adjustment/<int:aid>/decision',methods=['POST'])
@roles('Inventory Manager','Super User','Admin')
def adjustment_decision(aid):
    decision=request.form.get('decision');note=(request.form.get('decision_note') or '').strip()
    if decision not in ('approve','reject'):abort(400)
    if decision=='reject' and len(note)<5:abort(400,description='Provide a rejection reason.')
    c=db();row=c.execute('SELECT a.*,i.item_no FROM stock_adjustments a JOIN inventory i ON i.id=a.inventory_id WHERE a.id=?',(aid,)).fetchone()
    if not row:c.close();abort(404)
    if row['status']!='Pending Manager Approval':c.close();abort(409,description='Already decided.')
    stamp=now()
    changed=c.execute("UPDATE stock_adjustments SET status=?,decided_by=?,decided_at=?,decision_note=? WHERE id=? AND status='Pending Manager Approval'",('Approved' if decision=='approve' else 'Rejected',current_user()['id'],stamp,note,aid))
    if changed.rowcount!=1:c.rollback();c.close();abort(409)
    if decision=='approve':
        # Guard stale physical counts: manager must review again if balance changed.
        result=c.execute('UPDATE inventory SET qty=?,updated_at=? WHERE id=? AND qty=?',(row['proposed_qty'],stamp,row['inventory_id'],row['expected_qty']))
        if result.rowcount!=1:c.rollback();c.close();abort(409,description='Inventory changed since request; submit an updated adjustment.')
        delta=row['proposed_qty']-row['expected_qty']
        c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(row['inventory_id'],'in' if delta>0 else 'out',abs(delta),'Approved adjustment '+row['reference_no'],current_user()['id'],stamp))
    c.commit();c.close();audit('Stock adjustment '+decision+'d '+row['reference_no'],row['item_no']);flash('Adjustment decision recorded.','success');return redirect(url_for('asset_controls_page'))


# ECMCI Client Process: Procurement and lifecycle actions (v10 upgrade)
def client_ref(prefix):
    return prefix+'-'+datetime.now().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(4)

def client_whole(v, min_value=1):
    try:
        n=int(v)
        if n<min_value:raise ValueError()
        return n
    except (TypeError,ValueError):abort(400,description='Enter a valid nonnegative whole quantity.' if min_value==0 else 'Enter a positive whole quantity.')

@app.route('/procurement')
@roles('Super User','Admin','Inventory Manager','Requisition Officer','Encoder','Finance')
def procurement_page():
    c=db()
    prs=c.execute('SELECT p.*,u.name preparer,i.item_no FROM purchase_requisitions p LEFT JOIN users u ON u.id=p.prepared_by LEFT JOIN inventory i ON i.id=p.inventory_id ORDER BY p.id DESC LIMIT 200').fetchall()
    orders=c.execute('SELECT po.*,p.pr_no,p.description,p.quantity requested_quantity,p.inventory_id,v.name vendor_name FROM purchase_orders po JOIN purchase_requisitions p ON p.id=po.requisition_id JOIN vendors v ON v.id=po.vendor_id ORDER BY po.id DESC LIMIT 200').fetchall()
    receipts=c.execute('SELECT r.*,po.po_no FROM purchase_receipts r JOIN purchase_orders po ON po.id=r.purchase_order_id ORDER BY r.id DESC LIMIT 100').fetchall()
    vendors=c.execute("SELECT * FROM vendors WHERE status='Active' ORDER BY name").fetchall()
    c.close()
    return render_template('procurement.html',prs=prs,orders=orders,receipts=receipts,vendors=vendors)

@app.route('/procurement/requisition/<int:pid>/decision',methods=['POST'])
@roles('Super User','Admin','Inventory Manager')
def procurement_pr_decision(pid):
    action=request.form.get('decision');note=(request.form.get('note') or '').strip()
    if action not in ('approve','reject'):abort(400)
    if action=='reject' and len(note)<5:abort(400,description='A rejection reason is required.')
    c=db();pr=c.execute('SELECT * FROM purchase_requisitions WHERE id=?',(pid,)).fetchone()
    if not pr:c.close();abort(404)
    changed=c.execute("UPDATE purchase_requisitions SET status=?,approved_by=?,approved_at=?,approval_note=? WHERE id=? AND status='Pending Approval'",('Approved' if action=='approve' else 'Rejected',current_user()['id'],now(),note,pid))
    if changed.rowcount!=1:c.rollback();c.close();abort(409,description='Requisition already reviewed or cannot be changed.')
    c.commit();c.close();audit('Purchase requisition '+action+'d '+pr['pr_no']);flash('Requisition decision recorded.','success');return redirect(url_for('procurement_page'))

@app.route('/procurement/purchase-order',methods=['POST'])
@roles('Super User','Admin','Requisition Officer')
def procurement_create_order():
    pid=client_whole(request.form.get('requisition_id'));vid=client_whole(request.form.get('vendor_id'))
    try:
        price=float(request.form.get('unit_cost','0'))
        if not math.isfinite(price) or price<0:raise ValueError()
    except (ValueError,TypeError):abort(400,description='Unit cost must be a nonnegative amount.')
    c=db();pr=c.execute('SELECT * FROM purchase_requisitions WHERE id=?',(pid,)).fetchone()
    ven=c.execute("SELECT * FROM vendors WHERE id=? AND status='Active'",(vid,)).fetchone()
    if not pr or pr['status']!='Approved' or not ven:c.close();abort(400,description='Choose an approved requisition and active supplier.')
    if pr['inventory_id'] is None:c.close();abort(400,description='Link the requisition to an existing inventory item before issuing a stock purchase order.')
    if c.execute('SELECT id FROM purchase_orders WHERE requisition_id=?',(pid,)).fetchone():c.close();abort(409,description='A purchase order already exists for this requisition.')
    ref=client_ref('PO')
    c.execute('INSERT INTO purchase_orders(po_no,requisition_id,vendor_id,unit_cost,ordered_by,ordered_at,notes) VALUES(?,?,?,?,?,?,?)',(ref,pid,vid,price,current_user()['id'],now(),(request.form.get('notes') or '').strip()))
    c.execute("UPDATE purchase_requisitions SET status='Ordered' WHERE id=?",(pid,));c.commit();c.close();audit('Created purchase order '+ref);flash('Purchase order recorded.','success');return redirect(url_for('procurement_page'))

@app.route('/procurement/purchase-order/<int:oid>/receive',methods=['POST'])
@roles('Super User','Admin','Inventory Manager','Encoder')
def procurement_receive(oid):
    qty=client_whole(request.form.get('delivered_qty'));accepted=client_whole(request.form.get('accepted_qty'),0)
    if accepted>qty:abort(400,description='Accepted quantity cannot exceed delivered quantity.')
    reason=(request.form.get('condition_notes') or '').strip()
    if qty!=accepted and len(reason)<5:abort(400,description='Explain rejected or damaged units.')
    c=db();po=c.execute('SELECT o.*,p.inventory_id,p.quantity ordered_qty,p.pr_no FROM purchase_orders o JOIN purchase_requisitions p ON p.id=o.requisition_id WHERE o.id=?',(oid,)).fetchone()
    if not po:c.close();abort(404)
    if po['status'] not in ('Ordered','Partially Received'):c.close();abort(409,description='Purchase order is not open for receiving.')
    # Cap delivered units against the unfulfilled ordered quantity. No double receiving.
    remaining=po['ordered_qty']-po['received_qty']
    if qty>remaining:c.close();abort(409,description=f'Delivery exceeds remaining order quantity ({remaining}).')
    stamp=now();ref=client_ref('RCV')
    changed=c.execute('UPDATE purchase_orders SET received_qty=received_qty+?,status=? WHERE id=? AND received_qty=? AND status IN (?,?)',(qty,'Received' if qty==remaining else 'Partially Received',oid,po['received_qty'],'Ordered','Partially Received'))
    if changed.rowcount!=1:c.rollback();c.close();abort(409)
    c.execute('INSERT INTO purchase_receipts(receipt_no,purchase_order_id,quantity,accepted_qty,rejected_qty,received_by,received_at,condition_notes) VALUES(?,?,?,?,?,?,?,?)',(ref,oid,qty,accepted,qty-accepted,current_user()['id'],stamp,reason))
    if accepted:
        c.execute('UPDATE inventory SET qty=qty+?,updated_at=? WHERE id=?',(accepted,stamp,po['inventory_id']))
        c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(po['inventory_id'],'in',accepted,f'Purchase receiving {ref}; order {po["po_no"]}',current_user()['id'],stamp))
    if qty==remaining:c.execute("UPDATE purchase_requisitions SET status='Received' WHERE id=?",(po['requisition_id'],))
    c.commit();c.close();audit('Received purchase delivery '+ref);flash('Receipt saved. Only accepted units were added to inventory.','success');return redirect(url_for('procurement_page'))

@app.route('/asset-operations')
@roles('Super User','Admin','Inventory Manager','Encoder','Finance')
def asset_operations_page():
    c=db();items=c.execute('SELECT id,item_no,name,qty,condition FROM inventory ORDER BY name').fetchall()
    transfers=c.execute('SELECT t.*,i.item_no,i.name item_name FROM asset_transfers t JOIN inventory i ON i.id=t.inventory_id ORDER BY t.id DESC LIMIT 150').fetchall()
    repairs=c.execute('SELECT m.*,i.item_no,i.name item_name FROM asset_maintenance m JOIN inventory i ON i.id=m.inventory_id ORDER BY m.id DESC LIMIT 150').fetchall()
    c.close();return render_template('asset_operations.html',items=items,transfers=transfers,repairs=repairs)

@app.route('/asset-operations/transfer',methods=['POST'])
@roles('Super User','Admin','Inventory Manager','Encoder')
def asset_transfer_create():
    iid=client_whole(request.form.get('inventory_id'));qty=client_whole(request.form.get('quantity'))
    source=(request.form.get('from_department') or '').strip();dest=(request.form.get('to_department') or '').strip()
    kind=request.form.get('kind')
    if kind not in ('Transfer','Return') or not source or not dest or (source==dest and kind=='Transfer'):abort(400,description='Provide valid source/destination and transaction type.')
    c=db();item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
    if not item or qty>item['qty']:c.close();abort(400,description='Unknown item or insufficient stock to document transfer.')
    ref=client_ref('TRF' if kind=='Transfer' else 'RTN')
    c.execute('INSERT INTO asset_transfers(reference_no,inventory_id,quantity,from_department,to_department,kind,requested_by,requested_at,notes) VALUES(?,?,?,?,?,?,?,?,?)',(ref,iid,qty,source,dest,kind,current_user()['id'],now(),(request.form.get('notes') or '').strip()))
    c.commit();c.close();audit('Requested '+kind.lower()+' '+ref,item['item_no']);flash('Transfer/return queued for confirmation. Quantity unchanged until verified.','success');return redirect(url_for('asset_operations_page'))

@app.route('/asset-operations/transfer/<int:tid>/complete',methods=['POST'])
@roles('Super User','Admin','Inventory Manager')
def asset_transfer_complete(tid):
    c=db();row=c.execute('SELECT t.*,i.item_no FROM asset_transfers t JOIN inventory i ON i.id=t.inventory_id WHERE t.id=?',(tid,)).fetchone()
    if not row:c.close();abort(404)
    changed=c.execute("UPDATE asset_transfers SET status='Completed',completed_by=?,completed_at=? WHERE id=? AND status='Pending'",(current_user()['id'],now(),tid))
    if changed.rowcount!=1:c.rollback();c.close();abort(409,description='This transfer/return was already confirmed.')
    # This is a custody/location record. Inter-department transfers do not change total stock.
    c.commit();c.close();audit('Completed '+row['kind'].lower()+' '+row['reference_no'],row['item_no']);flash('Custody transfer/return confirmed; total inventory remains unchanged.','success');return redirect(url_for('asset_operations_page'))

@app.route('/asset-operations/maintenance',methods=['POST'])
@roles('Super User','Admin','Inventory Manager','Encoder')
def asset_maintenance_create():
    iid=client_whole(request.form.get('inventory_id'));description=(request.form.get('description') or '').strip()
    if len(description)<5:abort(400,description='Describe the maintenance work.')
    kind=request.form.get('kind');condition=request.form.get('condition_after')
    if kind not in ('Inspection','Repair','Maintenance','Damage Report') or condition not in ('Good','Needs Repair','Damaged','Under Maintenance'):abort(400,description='Invalid maintenance type or condition.')
    try:
        cost=float(request.form.get('cost','0'))
        if cost<0 or not math.isfinite(cost):raise ValueError()
    except (ValueError,TypeError):abort(400,description='Invalid maintenance cost.')
    stamp=request.form.get('performed_on') or date.today().isoformat()
    try:date.fromisoformat(stamp)
    except ValueError:abort(400,description='Invalid maintenance date.')
    c=db();item=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
    if not item:c.close();abort(404)
    ref=client_ref('MNT');c.execute('INSERT INTO asset_maintenance(reference_no,inventory_id,kind,condition_before,condition_after,description,cost,performed_on,recorded_by,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(ref,iid,kind,item['condition'],condition,description,cost,stamp,current_user()['id'],now()))
    c.execute('UPDATE inventory SET condition=?,updated_at=? WHERE id=?',(condition,now(),iid));c.commit();c.close();audit('Recorded asset maintenance '+ref,item['item_no']);flash('Maintenance history saved.','success');return redirect(url_for('asset_operations_page'))

@app.route('/client-reports')
@roles('Super User','Admin','Inventory Manager','Requisition Officer','Finance','Report Generator')
def client_reports():
    c=db();counts={}
    for label,table in [('Inventory','inventory'),('Movements','movements'),('Assignments','assignments'),('Audits','inventory_audits'),('Adjustments','stock_adjustments'),('Disposals','asset_disposals'),('Requisitions','purchase_requisitions'),('Purchase Orders','purchase_orders'),('Receipts','purchase_receipts'),('Transfers','asset_transfers'),('Maintenance','asset_maintenance')]:
        counts[label]=c.execute('SELECT COUNT(*) n FROM '+table).fetchone()['n']
    c.close();return render_template('client_reports.html',counts=counts)

CLIENT_REPORTS={
'inventory':('inventory','SELECT * FROM inventory'),
'movements':('movements','SELECT m.*,i.item_no,i.category FROM movements m JOIN inventory i ON i.id=m.inventory_id'),
'assignments':('assignments','SELECT a.*,i.item_no FROM assignments a JOIN inventory i ON i.id=a.inventory_id'),
'audits':('inventory_audit_items','SELECT a.audit_no,a.status audit_status,ai.*,i.item_no,i.category FROM inventory_audit_items ai JOIN inventory_audits a ON a.id=ai.audit_id JOIN inventory i ON i.id=ai.inventory_id'),
'adjustments':('stock_adjustments','SELECT a.*,i.item_no,i.category FROM stock_adjustments a JOIN inventory i ON i.id=a.inventory_id'),
'disposals':('asset_disposals','SELECT d.*,i.item_no,i.category FROM asset_disposals d JOIN inventory i ON i.id=d.inventory_id'),
'requisitions':('purchase_requisitions','SELECT * FROM purchase_requisitions'),
'purchase_orders':('purchase_orders','SELECT o.*,p.pr_no,v.name supplier FROM purchase_orders o JOIN purchase_requisitions p ON p.id=o.requisition_id JOIN vendors v ON v.id=o.vendor_id'),
'receipts':('purchase_receipts','SELECT r.*,o.po_no FROM purchase_receipts r JOIN purchase_orders o ON o.id=r.purchase_order_id'),
'transfers':('asset_transfers','SELECT t.*,i.item_no,i.category FROM asset_transfers t JOIN inventory i ON i.id=t.inventory_id'),
'maintenance':('asset_maintenance','SELECT m.*,i.item_no,i.category FROM asset_maintenance m JOIN inventory i ON i.id=m.inventory_id')}

@app.route('/client-reports/export/<kind>')
@roles('Super User','Admin','Inventory Manager','Requisition Officer','Finance','Report Generator')
def client_reports_export(kind):
    if kind not in CLIENT_REPORTS:abort(404)
    fmt=request.args.get('format','xlsx')
    if fmt not in ('xlsx','csv','pdf'):abort(400)
    table,sql=CLIENT_REPORTS[kind]
    # Bound filters preserve safe SQL: user values are never interpolated into a SQL clause.
    c=db();q=sql+' WHERE 1=1';args=[]
    date_column={'inventory':'received_date','movements':'m.created_at','assignments':'a.assigned_at','adjustments':'a.requested_at','disposals':'d.requested_at','requisitions':'created_at','purchase_orders':'o.ordered_at','receipts':'r.received_at','transfers':'t.requested_at','maintenance':'m.performed_on'} .get(kind)
    for key,operator in [('date_from','>='),('date_to','<=')]:
        val=request.args.get(key,'').strip()
        if val and date_column:
            try:date.fromisoformat(val)
            except ValueError:c.close();abort(400,description='Invalid report date.')
            q+=f' AND substr({date_column},1,10) {operator} ?';args.append(val)
    category=request.args.get('category','').strip()
    if category and kind in ('inventory','movements','audits','adjustments','disposals','transfers','maintenance'):
        col='category' if kind=='inventory' else 'i.category'
        q+=f' AND {col}=?';args.append(category)
    department=request.args.get('department','').strip()
    dept_col={'inventory':'custodian','assignments':'a.department','transfers':'t.to_department'}.get(kind)
    if department and dept_col:q+=f' AND {dept_col}=?';args.append(department)
    employee=request.args.get('employee','').strip()
    if employee:
        try:employee_id=int(employee)
        except (ValueError,TypeError):c.close();abort(400,description='Invalid employee ID.')
        emp_col={'assignments':'a.employee_id','adjustments':'a.requested_by','disposals':'d.requested_by','transfers':'t.requested_by','maintenance':'m.recorded_by'}.get(kind)
        if emp_col:q+=f' AND {emp_col}=?';args.append(employee_id)
    status=request.args.get('status','').strip()
    status_col={'inventory':'condition','assignments':'a.status','adjustments':'a.status','disposals':'d.status','requisitions':'status','purchase_orders':'o.status','transfers':'t.status'}.get(kind)
    if status and status_col:q+=f' AND {status_col}=?';args.append(status)
    rows=c.execute(q+' LIMIT 10000',tuple(args)).fetchall();c.close()
    headers=list(rows[0].keys()) if rows else []
    if not headers:
        # Empty report: supply column names from table using a zero-row query.
        c=db();cursor=c.execute(sql+' WHERE 1=0');headers=[d[0] for d in cursor.description];c.close()
    if fmt=='pdf':
        # A real dataset PDF, not browser-printing the overview page.
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
        from reportlab.lib.utils import simpleSplit
        from xml.sax.saxutils import escape
        out=BytesIO();page=landscape(A4)
        doc=SimpleDocTemplate(out,pagesize=page,rightMargin=22,leftMargin=22,topMargin=28,bottomMargin=28)
        styles=getSampleStyleSheet()
        story=[Paragraph('ECMCI | '+escape(kind.replace('_',' ').title())+' Report',styles['Title']),Paragraph('Generated: '+now()+' | Records: '+str(len(rows)),styles['Normal']),Spacer(1,12)]
        # Restrict width to printable A4 while retaining all data columns.
        # Wide records are split across multiple pages of columns rather than clipped.
        max_columns=6
        for start in range(0,len(headers),max_columns):
            columns=headers[start:start+max_columns]
            if not columns:continue
            story.append(Paragraph('Columns '+str(start+1)+'–'+str(start+len(columns)),styles['Heading3']))
            data=[[Paragraph(escape(str(h)),styles['BodyText']) for h in columns]]
            for r in rows:
                data.append([Paragraph(escape(str(r[h]) if r[h] is not None else '')[:180],styles['BodyText']) for h in columns])
            width=(page[0]-44)/len(columns)
            t=LongTable(data,colWidths=[width]*len(columns),repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eff8')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#cbd5e1')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.append(t);story.append(Spacer(1,14))
        doc.build(story);out.seek(0)
        return send_file(out,as_attachment=True,download_name=f'ECMCI_{kind}.pdf',mimetype='application/pdf')
    if fmt=='csv':
        output=StringIO();w=csv.writer(output);w.writerow(headers)
        for r in rows:w.writerow([r[h] for h in headers])
        return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="ECMCI_{kind}.csv"'})
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.title=kind.replace('_',' ').title()[:31];ws.append(headers)
    for r in rows:ws.append([r[h] for h in headers])
    bio=BytesIO();wb.save(bio);bio.seek(0)
    return send_file(bio,as_attachment=True,download_name=f'ECMCI_{kind}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.errorhandler(409)
def conflict(e):return render_template('error.html',code=409,title='Record cannot be changed',message=getattr(e,'description','Refresh the page and try again.')),409

@app.errorhandler(400)
def bad_request(e):return render_template('error.html',code=400,title='Request could not be processed',message=getattr(e,'description','Invalid request.')),400
@app.errorhandler(403)
def forbidden(e):return render_template('error.html',code=403,title='Access restricted',message='Your account does not have permission to view or change this area.'),403
@app.errorhandler(404)
def not_found(e):return render_template('error.html',code=404,title='Not found',message='The requested record or page could not be found.'),404
@app.errorhandler(500)
def server_error(e):logger.exception('Unhandled application error');return render_template('error.html',code=500,title='Something went wrong',message='The system encountered an unexpected error. Check the server logs for details.'),500

init_db()

if __name__=='__main__':
    app.run(host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT',5000)),debug=False)
