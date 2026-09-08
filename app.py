from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta, date
from io import BytesIO, StringIO
from pathlib import Path
import sqlite3, os, csv, math, secrets, logging, time

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'inharitense.db'
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

CATEGORIES=['PPE & Infection Control','Health & Safety','Office Operations','IT & BPO Equipment','Facility & Sanitation']
ROLE_LABELS={'HR':'HR / Admin','Purchasing':'Purchasing / Procurement','IT Custodian':'IT Custodian','Department User':'Department Employee'}
ROLE_CATEGORIES={'HR':CATEGORIES,'Purchasing':CATEGORIES,'IT Custodian':['IT & BPO Equipment'],'Department User':['Office Operations']}
DEFAULT_USERS=[('HR Head','hr@ecmci.com','HR','All','hr123'),('Purchasing Officer','purchasing@ecmci.com','Purchasing','Procurement','purchase123'),('IT Custodian','it@ecmci.com','IT Custodian','IT & BPO Equipment','it123'),('Department Employee','employee@ecmci.com','Department User','Office Operations','employee123')]
DEFAULT_INVENTORY=[
('PPE-001','ECMCI-PPE-001','Surgical Masks (box)','PPE & Infection Control','box',42,60,18,450,'MedSure Supplies PH','HR / Admin','Good','2026-06-02',None),('PPE-002','ECMCI-PPE-002','Nitrile Gloves (box)','PPE & Infection Control','box',18,40,15,380,'MedSure Supplies PH','HR / Admin','Good','2026-06-02',None),('PPE-003','ECMCI-PPE-003','Alcohol / Hand Sanitizer (500ml)','PPE & Infection Control','bottle',26,40,10,120,'MedSure Supplies PH','HR / Admin','Good','2026-05-10','2026-09-20'),('PPE-004','ECMCI-PPE-004','Disinfectant Wipes (pack)','PPE & Infection Control','pack',12,30,12,95,'CleanPro Solutions','HR / Admin','Good','2026-05-10','2027-01-15'),
('HSE-001','ECMCI-HSE-001','First Aid Kit','Health & Safety','kit',6,10,3,850,'SafeCare Equipment','HR / Admin','Good','2026-03-18',None),('HSE-002','ECMCI-HSE-002','Digital Thermometer','Health & Safety','piece',8,12,4,350,'SafeCare Equipment','HR / Admin','Good','2026-03-18',None),('HSE-003','ECMCI-HSE-003','Disposable Face Shield','Health & Safety','piece',14,25,8,60,'SafeCare Equipment','HR / Admin','Good','2026-04-22',None),
('OFF-001','ECMCI-OFF-001','Bond Paper (ream)','Office Operations','ream',58,100,25,220,'OfficeHub Philippines','Purchasing','Good','2026-07-01',None),('OFF-002','ECMCI-OFF-002','Printer Ink Cartridge','Office Operations','cartridge',14,25,7,650,'OfficeHub Philippines','Purchasing','Good','2026-07-01',None),('OFF-003','ECMCI-OFF-003','Ballpen (box)','Office Operations','box',9,40,12,150,'OfficeHub Philippines','Purchasing','Good','2026-06-15',None),
('ITB-001','ECMCI-ITB-001','Headset','IT & BPO Equipment','piece',32,45,15,1200,'TechServe BPO Systems','IT Custodian','Good','2026-02-10',None),('ITB-002','ECMCI-ITB-002','Laptop (Dell Latitude)','IT & BPO Equipment','piece',24,30,8,32000,'TechServe BPO Systems','IT Custodian','Good','2026-01-20',None),('ITB-003','ECMCI-ITB-003','LCD Monitor 24"','IT & BPO Equipment','piece',12,30,15,6500,'TechServe BPO Systems','IT Custodian','Good','2026-01-20',None),
('FAC-001','ECMCI-FAC-001','Tissue (pack)','Facility & Sanitation','pack',65,80,20,85,'CleanPro Solutions','Purchasing','Good','2026-07-20',None),('FAC-002','ECMCI-FAC-002','Heavy-Duty Trash Bags (roll)','Facility & Sanitation','roll',18,30,10,180,'CleanPro Solutions','Purchasing','Good','2026-07-20',None),('FAC-003','ECMCI-FAC-003','Surface Disinfectant (1L)','Facility & Sanitation','bottle',7,15,6,150,'CleanPro Solutions','Purchasing','Good','2026-06-05','2026-09-25')]
DEFAULT_VENDORS=[('MedSure Supplies PH','PPE & Infection Control','Masks, Gloves, Sanitizer','Active'),('CleanPro Solutions','Facility & Sanitation','Wipes, Disinfectant, Tissue','Active'),('OfficeHub Philippines','Office Operations','Paper, Ink, Ballpen','Active'),('TechServe BPO Systems','IT & BPO Equipment','Headsets, Laptops, Monitors','Active'),('SafeCare Equipment','Health & Safety','First Aid, Thermometers','Active')]

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
    CREATE INDEX IF NOT EXISTS idx_movements_created ON movements(created_at); CREATE INDEX IF NOT EXISTS idx_movements_item ON movements(inventory_id); CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
    '''

def init_db():
    c=db(); c.executescript(schema())
    count=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
    bootstrap_email=os.environ.get('BOOTSTRAP_ADMIN_EMAIL','').strip().lower(); bootstrap_pw=os.environ.get('BOOTSTRAP_ADMIN_PASSWORD',''); bootstrap_name=os.environ.get('BOOTSTRAP_ADMIN_NAME','HR Administrator').strip()
    if count==0:
        if IS_PRODUCTION:
            if not bootstrap_email or not bootstrap_pw: raise RuntimeError('Production database is empty. Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD for the first HR account.')
            users=[(bootstrap_name,bootstrap_email,'HR','All',bootstrap_pw)]
        else: users=DEFAULT_USERS
        for name,email,role,dept,pw in users:c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',(name,email,generate_password_hash(pw),role,dept,now()))
    if c.execute('SELECT COUNT(*) n FROM inventory').fetchone()['n']==0 and not IS_PRODUCTION:
        for r in DEFAULT_INVENTORY:c.execute('INSERT INTO inventory(item_no,code,name,category,unit,qty,max_qty,min_qty,cost,vendor,custodian,condition,received_date,expiry,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*r,now()))
    if c.execute('SELECT COUNT(*) n FROM vendors').fetchone()['n']==0 and not IS_PRODUCTION:
        for r in DEFAULT_VENDORS:c.execute('INSERT INTO vendors(name,category,supplies,status,updated_at) VALUES(?,?,?,?,?)',(*r,now()))
    if c.execute('SELECT COUNT(*) n FROM movements').fetchone()['n']==0 and not IS_PRODUCTION:
        uid=c.execute("SELECT id FROM users WHERE role='HR' LIMIT 1").fetchone()['id'];items=c.execute('SELECT id FROM inventory ORDER BY id').fetchall();seed=[(0,'in',8),(0,'out',3),(1,'out',4),(2,'out',2),(3,'in',5),(3,'out',3),(4,'out',1),(7,'out',7),(8,'out',3),(9,'out',4),(10,'out',2),(11,'out',2),(12,'out',1),(13,'in',6),(14,'out',4),(15,'out',2),(0,'out',4),(1,'in',10),(7,'out',5),(10,'out',1)]
        for idx,(item_idx,typ,q) in enumerate(seed):
            d=datetime.now()-timedelta(days=6-(idx%7),hours=(idx*3)%12); item=items[item_idx%len(items)];c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(item['id'],typ,q,'Demo historical transaction',uid,d.isoformat(timespec='seconds')))
    c.commit();c.close()

# ---- Security ----
def csrf_token():
    if not session.get('_csrf'): session['_csrf']=secrets.token_urlsafe(32)
    return session['_csrf']
app.jinja_env.globals['csrf_token']=csrf_token

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
    c=db();u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(uid,)).fetchone();c.close();return u

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

def forecast_for(item,lead=None,safety=None):
    c=db();rows=c.execute("SELECT quantity,created_at FROM movements WHERE inventory_id=? AND movement_type='out' ORDER BY created_at DESC LIMIT 180",(item['id'],)).fetchall();c.close();cutoff=datetime.now()-timedelta(days=30);used=sum(r['quantity'] for r in rows if _parse_dt(r['created_at'])>=cutoff);daily=used/30 if used else max((item['max_qty']-item['qty'])/30,0.1)
    # Lead time and safety stock are now adjustable (HR/Purchasing can tune them on the Forecast
    # page); they fall back to sensible defaults (5-day lead, max(min_qty,3) safety) when not supplied.
    safety=safety if safety is not None else max(item['min_qty'],3);lead=lead if lead is not None else 5;review=14;days=max(0,(item['qty']-safety)/max(daily,.1));recommended=max(1,math.ceil(daily*(lead+review)));return {'daily':round(daily,2),'days_to_reorder':round(days,1),'recommended':recommended,'lead_time':lead,'safety':safety,'urgent':days<=lead+3,'sample_days':30}
def _parse_dt(s):
    try:return datetime.fromisoformat(s)
    except:return datetime.min

def dashboard_payload():
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();inv=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();value=sum(x['qty']*x['cost'] for x in inv);low=[x for x in inv if x['qty']<=x['min_qty'] and x['qty']>0];out=[x for x in inv if x['qty']==0];exp=[x for x in inv if x['expiry'] and x['expiry']<= (date.today()+timedelta(days=30)).isoformat()]
    if u['role']=='HR':pending=c.execute("SELECT COUNT(*) n FROM requests WHERE status='Forwarded to HR'").fetchone()['n']
    elif u['role']=='Purchasing':pending=c.execute("SELECT COUNT(*) n FROM requests WHERE status='For Review'").fetchone()['n']
    else:pending=c.execute("SELECT COUNT(*) n FROM requests WHERE requester_id=? AND status NOT IN ('Fulfilled','Rejected by Purchasing','Rejected by HR')",(u['id'],)).fetchone()['n']
    recent=c.execute(f'SELECT m.*,i.name,i.item_no,i.unit,u.name by_name FROM movements m JOIN inventory i ON i.id=m.inventory_id LEFT JOIN users u ON u.id=m.by_user WHERE i.category IN ({ph}) ORDER BY m.created_at DESC LIMIT 12',cats).fetchall();days=[]
    for n in range(6,-1,-1):
        d=date.today()-timedelta(days=n);start=d.isoformat();end=(d+timedelta(days=1)).isoformat();r=c.execute(f"SELECT COALESCE(SUM(CASE WHEN m.movement_type='in' THEN quantity ELSE 0 END),0) ins,COALESCE(SUM(CASE WHEN m.movement_type='out' THEN quantity ELSE 0 END),0) outs,COUNT(*) cnt FROM movements m JOIN inventory i ON i.id=m.inventory_id WHERE i.category IN ({ph}) AND m.created_at>=? AND m.created_at<?",(*cats,start,end)).fetchone();days.append({'label':d.strftime('%b %d'),'in':r['ins'],'out':r['outs'],'count':r['cnt']})
    bycat=[]
    for cat in cats:
        r=c.execute('SELECT COALESCE(SUM(qty),0) qty,COALESCE(SUM(min_qty),0) min_qty,COUNT(*) items FROM inventory WHERE category=?',(cat,)).fetchone();bycat.append({'category':cat,'qty':r['qty'],'min':r['min_qty'],'items':r['items']})
    health={'healthy':sum(1 for x in inv if x['qty']>x['min_qty']),'reorder':sum(1 for x in inv if 0<x['qty']<=x['min_qty']),'out':len(out)};requests_count=c.execute("SELECT COUNT(*) n FROM requests WHERE status IN ('For Review','Forwarded to HR','Approved')").fetchone()['n'];unread=c.execute("SELECT COUNT(*) n FROM notifications WHERE read_flag=0 AND (recipient_role=? OR recipient_user=?)",(u['role'],u['id'])).fetchone()['n'];c.close();return {'total_items':len(inv),'categories':len(cats),'low':len(low),'out':len(out),'expiring':len(exp),'pending':pending,'pending_all':requests_count,'value':round(value,2),'movements':days,'category_levels':bycat,'health':health,'recent':[dict(x) for x in recent],'unread':unread}

@app.context_processor
def inject():
    u=current_user()
    cats=ROLE_CATEGORIES[u['role']] if u else CATEGORIES
    counts={}
    if u:
        c=db();rows=c.execute('SELECT category, COUNT(*) n FROM inventory GROUP BY category').fetchall();c.close()
        counts={r['category']:r['n'] for r in rows}
    return {'me':u,'role_labels':ROLE_LABELS,'categories':cats,'category_counts':counts}

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user():return redirect(url_for('dashboard'))
    if request.method=='POST':
        ip=request.remote_addr or 'unknown'
        if not login_allowed(ip):flash('Too many failed attempts. Try again in 5 minutes.','error');return render_template('login.html'),429
        email=request.form.get('email','').strip().lower();pw=request.form.get('password','');c=db();u=c.execute('SELECT * FROM users WHERE lower(email)=? AND active=1',(email,)).fetchone()
        if not u or not check_password_hash(u['password_hash'],pw):c.close();record_login_failure(ip);flash('Invalid email or password.','error')
        else:
            LOGIN_ATTEMPTS.pop(ip,None);c.execute('UPDATE users SET last_login=? WHERE id=?',(now(),u['id']));c.commit();c.close();session.clear();session['user_id']=u['id'];session.permanent=True;csrf_token();audit('Signed in to the inventory system');return redirect(url_for('dashboard'))
    return render_template('login.html')
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
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();items=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();vendors=c.execute('SELECT name FROM vendors WHERE status="Active" ORDER BY name').fetchall();c.close()
    selected_category=request.args.get('category','')
    if selected_category not in cats:selected_category=''
    return render_template('inventory.html',items=[dict(x) for x in items],vendors=vendors,can_edit=u['role'] in ('HR','Purchasing','IT Custodian'),selected_category=selected_category)

CATEGORY_PREFIX={'PPE & Infection Control':'PPE','Health & Safety':'HSE','Office Operations':'OFF','IT & BPO Equipment':'ITB','Facility & Sanitation':'FAC'}
@app.route('/api/inventory/next-code')
@login_required
def api_next_code():
    """Suggests the next item number for a category (e.g. PPE-005), matching the existing
    naming convention, so HR/Purchasing/IT don't have to invent one by hand. Still editable —
    this is a suggestion, not a lock."""
    cat=(request.args.get('category') or '').strip()
    prefix=CATEGORY_PREFIX.get(cat)
    if not prefix or not allowed(cat):return jsonify(error='Unknown or unauthorized category.'),400
    c=db();rows=c.execute("SELECT item_no FROM inventory WHERE item_no LIKE ?",(f'{prefix}-%',)).fetchall();c.close()
    nums=[]
    for r in rows:
        tail=r['item_no'].split('-')[-1]
        if tail.isdigit():nums.append(int(tail))
    next_n=(max(nums)+1) if nums else 1
    item_no=f'{prefix}-{next_n:03d}'
    return jsonify(item_no=item_no,code=f'ECMCI-{item_no}')
@app.route('/api/inventory',methods=['POST'])
@login_required
def api_inventory_save():
    u=current_user();data=request.get_json(silent=True) or request.form;iid=data.get('id');cat=(data.get('category') or '').strip()
    if u['role'] not in ('HR','Purchasing','IT Custodian') or not allowed(cat):return jsonify(error='You do not have permission for this category.'),403
    try:qty=max(0,int(data.get('qty',0)));maxq=max(1,int(data.get('max_qty',1)));minq=max(0,int(data.get('min_qty',0)));cost=float(data.get('cost',0) or 0)
    except:return jsonify(error='Invalid numeric values.'),400
    item_no=(data.get('item_no') or '').strip();name=(data.get('name') or '').strip();code=(data.get('code') or '').strip() or None
    if not item_no or not name:return jsonify(error='Item number and name are required.'),400
    c=db();dup=c.execute('SELECT id FROM inventory WHERE (lower(item_no)=lower(?) OR lower(name)=lower(?) OR (code IS NOT NULL AND lower(code)=lower(?))) AND id<>COALESCE(?,0)',(item_no,name,code,iid or 0)).fetchone()
    if dup:c.close();return jsonify(error='Duplicate item number, name, or code.'),409
    vals=(item_no,code,name,cat,data.get('unit') or 'piece',qty,maxq,minq,cost,data.get('vendor') or '',data.get('custodian') or '',data.get('condition') or 'Good',data.get('received_date') or None,data.get('expiry') or None,now())
    if iid:
        old=c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone()
        if not old:c.close();return jsonify(error='Item not found.'),404
        c.execute('UPDATE inventory SET item_no=?,code=?,name=?,category=?,unit=?,qty=?,max_qty=?,min_qty=?,cost=?,vendor=?,custodian=?,condition=?,received_date=?,expiry=?,updated_at=? WHERE id=?',(*vals,iid));action='Updated inventory item'
    else:
        c.execute('INSERT INTO inventory(item_no,code,name,category,unit,qty,max_qty,min_qty,cost,vendor,custodian,condition,received_date,expiry,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals);action='Created inventory item';iid=c.execute('SELECT id FROM inventory WHERE item_no=?',(item_no,)).fetchone()['id']
    c.commit();c.close();audit(f'{action}: {name}',item_no);return jsonify(ok=True,id=iid,message='Inventory saved.')
@app.route('/api/inventory/<int:iid>',methods=['DELETE'])
@login_required
def api_inventory_delete(iid):
    u=current_user();item=get_item(iid)
    if not item or u['role'] not in ('HR','Purchasing','IT Custodian') or not allowed(item['category']):return jsonify(error='Not allowed.'),403
    c=db();has_moves=c.execute('SELECT 1 FROM movements WHERE inventory_id=? LIMIT 1',(iid,)).fetchone();has_req=c.execute('SELECT 1 FROM requests WHERE inventory_id=? LIMIT 1',(iid,)).fetchone()
    if has_moves or has_req:c.close();return jsonify(error='This item has transaction history and cannot be deleted. Archive it instead.'),409
    c.execute('DELETE FROM inventory WHERE id=?',(iid,));c.commit();c.close();audit(f'Deleted inventory item: {item["name"]}',item['item_no']);return jsonify(ok=True)
@app.route('/api/movement',methods=['POST'])
@login_required
def api_movement():
    u=current_user();data=request.get_json(silent=True) or request.form
    try:iid=int(data.get('inventory_id'));qty=max(1,int(data.get('quantity',1)))
    except:return jsonify(error='Invalid item or quantity.'),400
    typ=data.get('movement_type');item=get_item(iid)
    if typ not in ('in','out') or not item or u['role'] not in ('HR','Purchasing','IT Custodian') or not allowed(item['category']):return jsonify(error='Movement not permitted.'),403
    if typ=='out' and qty>item['qty']:return jsonify(error=f'Only {item["qty"]} {item["unit"]} available.'),409
    newq=item['qty']+qty if typ=='in' else item['qty']-qty;c=db();stamp=now();c.execute('UPDATE inventory SET qty=?,times_out=times_out+?,updated_at=? WHERE id=?',(newq,qty if typ=='out' else 0,stamp,iid));c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(iid,typ,qty,(data.get('note') or '').strip(),u['id'],stamp));c.commit();c.close();audit(f'Stock {typ.upper()}: {item["name"]} x{qty}',item['item_no']);return jsonify(ok=True,qty=newq,message=f'Stock {typ.upper()} recorded.')

@app.route('/requests')
@login_required
def requests_page():
    u=current_user();c=db();
    if u['role'] in ('HR','Purchasing'):rows=c.execute('SELECT r.*,i.name item_name,i.item_no,i.unit,u.name requester,u.email requester_email FROM requests r JOIN inventory i ON i.id=r.inventory_id JOIN users u ON u.id=r.requester_id ORDER BY r.created_at DESC').fetchall()
    else:rows=c.execute('SELECT r.*,i.name item_name,i.item_no,i.unit,u.name requester,u.email requester_email FROM requests r JOIN inventory i ON i.id=r.inventory_id JOIN users u ON u.id=r.requester_id WHERE requester_id=? ORDER BY r.created_at DESC',(u['id'],)).fetchall()
    cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));items=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY name',cats).fetchall();c.close();return render_template('requests.html',requests=rows,items=items)
@app.route('/requests/create',methods=['POST'])
@login_required
def request_create():
    u=current_user()
    if u['role'] in ('HR','Purchasing'):abort(403)
    try:iid=int(request.form.get('inventory_id'));qty=max(1,int(request.form.get('quantity',1)))
    except:flash('Enter a valid quantity.','error');return redirect(url_for('requests_page'))
    item=get_item(iid)
    if not item or not allowed(item['category']):abort(403)
    reqno=f'REQ-{datetime.now().strftime("%Y%m%d%H%M%S")}-{secrets.token_hex(2).upper()}';c=db();c.execute('INSERT INTO requests(request_no,inventory_id,quantity,purpose,requester_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(reqno,iid,qty,(request.form.get('purpose') or '').strip(),u['id'],'For Review',now(),now()));c.commit();c.close();notify('Purchasing','New stock request',f'{reqno} · {item["name"]} · {qty} {item["unit"]}','request');audit(f'Submitted stock request: {item["name"]}',item['item_no']);flash(f'{reqno} sent to Purchasing.','success');return redirect(url_for('requests_page'))
@app.route('/requests/<int:rid>/action',methods=['POST'])
@login_required
def request_action(rid):
    u=current_user();action=request.form.get('action');note=(request.form.get('note') or '').strip();c=db();r=c.execute('SELECT r.*,i.name item_name,i.item_no,i.qty current_qty,i.unit FROM requests r JOIN inventory i ON i.id=r.inventory_id WHERE r.id=?',(rid,)).fetchone()
    if not r:c.close();abort(404)
    status=None
    if action=='endorse' and u['role']=='Purchasing' and r['status']=='For Review':status='Forwarded to HR';notify('HR','Request ready for approval',f'{r["request_no"]} · {r["item_name"]} is ready for final approval.','approval',conn=c)
    elif action=='reject_purchasing' and u['role']=='Purchasing' and r['status']=='For Review':status='Rejected by Purchasing';notify('', 'Request rejected', f'{r["request_no"]} was rejected by Purchasing.','error',user_id=r['requester_id'],conn=c)
    elif action=='approve' and u['role']=='HR' and r['status']=='Forwarded to HR':status='Approved';notify('', 'Request approved', f'{r["request_no"]} is approved and ready for fulfillment.','success',user_id=r['requester_id'],conn=c)
    elif action=='reject_hr' and u['role']=='HR' and r['status']=='Forwarded to HR':status='Rejected by HR';notify('', 'Request rejected', f'{r["request_no"]} was rejected by HR.','error',user_id=r['requester_id'],conn=c)
    elif action=='fulfill' and u['role']=='HR' and r['status']=='Approved':
        if r['quantity']>r['current_qty']:c.close();flash('Cannot fulfill: insufficient stock.','error');return redirect(url_for('requests_page'))
        status='Fulfilled';stamp=now();c.execute('UPDATE inventory SET qty=qty-?,updated_at=? WHERE id=?',(r['quantity'],stamp,r['inventory_id']));c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(r['inventory_id'],'out',r['quantity'],f'Fulfilled {r["request_no"]}',u['id'],stamp));notify('', 'Request fulfilled', f'{r["request_no"]} · {r["item_name"]} was fulfilled.','success',user_id=r['requester_id'],conn=c)
    elif action=='note' and u['role'] in ('HR','Purchasing'):
        col='hr_note' if u['role']=='HR' else 'purchasing_note';c.execute(f'UPDATE requests SET {col}=?,updated_at=? WHERE id=?',(note,now(),rid));c.commit();c.close();audit(f'Updated request note: {r["request_no"]}',r['item_no']);flash('Note saved.','success');return redirect(url_for('requests_page'))
    else:c.close();abort(403)
    stamp=now()
    if status:
        if u['role']=='Purchasing':c.execute("UPDATE requests SET status=?,purchasing_note=COALESCE(NULLIF(?,''),purchasing_note),purchasing_by=?,purchasing_at=?,updated_at=? WHERE id=?",(status,note,u['id'],stamp,stamp,rid))
        else:c.execute("UPDATE requests SET status=?,hr_note=COALESCE(NULLIF(?,''),hr_note),hr_by=?,hr_at=?,updated_at=? WHERE id=?",(status,note,u['id'],stamp,stamp,rid))
        c.commit();c.close();audit(f'{status}: {r["item_name"]}',r['item_no']);flash(f'Request {status.lower()}.','success')
    return redirect(url_for('requests_page'))

@app.route('/vendors')
@login_required
@roles('Purchasing')
def vendors_page():
    c=db();vendors=c.execute('SELECT * FROM vendors ORDER BY category,name').fetchall();c.close();return render_template('vendors.html',vendors=vendors)
@app.route('/vendors/save',methods=['POST'])
@login_required
@roles('Purchasing')
def vendor_save():
    name=(request.form.get('name') or '').strip()
    if not name:flash('Vendor name is required.','error');return redirect(url_for('vendors_page'))
    c=db()
    try:c.execute('INSERT INTO vendors(name,category,supplies,status,contact,email,updated_at) VALUES(?,?,?,?,?,?,?)',(name,request.form.get('category'),request.form.get('supplies'),request.form.get('status','Active'),request.form.get('contact'),request.form.get('email'),now()));c.commit();audit(f'Created vendor: {name}');flash('Vendor added.','success')
    except Exception:c.rollback();flash('That vendor already exists or could not be saved.','error')
    c.close();return redirect(url_for('vendors_page'))
@app.route('/users')
@login_required
@roles('HR')
def users_page():
    c=db();users=c.execute('SELECT * FROM users ORDER BY name').fetchall();audits=c.execute('SELECT a.*,u.name user_name,u.role FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 100').fetchall();c.close();return render_template('users.html',users=users,audits=audits)
@app.route('/users/create',methods=['POST'])
@login_required
@roles('HR')
def user_create():
    name=(request.form.get('name') or '').strip();email=(request.form.get('email') or '').strip().lower();role=request.form.get('role');dept=request.form.get('department','')
    if role not in ROLE_LABELS or not name or not email:flash('Complete the user details.','error');return redirect(url_for('users_page'))
    c=db()
    try:c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',(name,email,generate_password_hash(os.environ.get('DEFAULT_TEMP_PASSWORD','ECMCI@Welcome1')),role,dept,now()));c.commit();audit(f'Created user: {name}');flash('User created with the configured temporary password.','success')
    except Exception:c.rollback();flash('That email already exists or could not be saved.','error')
    c.close();return redirect(url_for('users_page'))
@app.route('/users/<int:uid>/toggle',methods=['POST'])
@login_required
@roles('HR')
def user_toggle(uid):
    if current_user()['id']==uid:flash('You cannot disable your own account.','error');return redirect(url_for('users_page'))
    c=db();c.execute('UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(uid,));c.commit();c.close();audit(f'Toggled user account: {uid}');return redirect(url_for('users_page'))

@app.route('/forecast')
@login_required
@roles('HR','Purchasing')
def forecast_page():
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();items=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();c.close();return render_template('forecast.html',items=items)
@app.route('/api/forecast/<int:iid>')
@login_required
@roles('HR','Purchasing')
def forecast_api(iid):
    item=get_item(iid)
    if not item or not allowed(item['category']):abort(403)
    try:lead=int(request.args['lead']) if 'lead' in request.args else None
    except (ValueError,KeyError):lead=None
    try:safety=int(request.args['safety']) if 'safety' in request.args else None
    except (ValueError,KeyError):safety=None
    cutoff=(datetime.now()-timedelta(days=30)).isoformat(timespec='seconds');c=db();rows=c.execute("SELECT SUBSTR(created_at,1,10) d,SUM(CASE WHEN movement_type='out' THEN quantity ELSE 0 END) outs,SUM(CASE WHEN movement_type='in' THEN quantity ELSE 0 END) ins FROM movements WHERE inventory_id=? AND created_at>=? GROUP BY SUBSTR(created_at,1,10) ORDER BY d",(iid,cutoff)).fetchall();c.close();f=forecast_for(item,lead=lead,safety=safety);return jsonify({'item':dict(item),'forecast':f,'history':[dict(r) for r in rows]})
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
    u=current_user();cats=ROLE_CATEGORIES[u['role']];ph=','.join('?'*len(cats));c=db();rows=c.execute(f'SELECT * FROM inventory WHERE category IN ({ph}) ORDER BY category,name',cats).fetchall();c.close();wb=Workbook();ws=wb.active;ws.title='Inventory Report';headers=['Item No.','Item','Category','Unit','On Hand','Minimum','Maximum','Unit Cost (PHP)','Vendor','Custodian','Status'];ws.append(headers)
    for r in rows:ws.append([r['item_no'],r['name'],r['category'],r['unit'],r['qty'],r['min_qty'],r['max_qty'],r['cost'],r['vendor'],r['custodian'],'Low stock' if r['qty']<=r['min_qty'] else 'Healthy'])
    for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(max(max(len(str(x.value or '')) for x in col)+2,12),34)
    buf=BytesIO();wb.save(buf);buf.seek(0);return send_file(buf,as_attachment=True,download_name='ECMCI_Inventory_Report.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
@app.route('/api/dashboard')
@login_required
def api_dashboard():return jsonify(dashboard_payload())
@app.route('/api/scan')
@login_required
def api_scan():
    q=request.args.get('q','').strip().lower();c=db();item=c.execute('SELECT * FROM inventory WHERE lower(item_no)=? OR lower(code)=?',(q,q)).fetchone();c.close()
    if not item or not allowed(item['category']):return jsonify(found=False),404
    return jsonify(found=True,item=dict(item))

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
