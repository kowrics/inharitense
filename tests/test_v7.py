"""Backend authorization and persistence regression checks."""
import pytest,csv,io,secrets
from datetime import date,timedelta
from tests.conftest import get_csrf_token
from tests.test_refinements import create_item,make_audit
ACCOUNTS={'Super User':('admin@ecmci.com','admin123'),'Encoder':('encoder@ecmci.com','encoder123'),'Report Generator':('reports@ecmci.com','report123'),'Employee':('employee@ecmci.com','employee123')}

def role_client(app,role):
 c=app.test_client();email,password=ACCOUNTS[role]
 assert c.post('/login',data=dict(email=email,password=password)).status_code==302
 return c

PAGES={'/':set(ACCOUNTS),'/settings':set(ACCOUNTS),'/inventory':{'Super User','Encoder'},'/inventory-audit':{'Super User','Encoder'},'/forecast':{'Super User','Encoder','Report Generator'},'/reports-v4':{'Super User','Report Generator'},'/vendors':{'Super User'},'/users':{'Super User'},'/requisitions':{'Super User','Encoder'},'/lifecycle':{'Super User'},'/assignments':{'Super User','Encoder','Employee'},'/requests':{'Super User','Encoder','Employee'},'/reports/stock':{'Super User','Report Generator'},'/reports/xlsx/movements':{'Super User','Report Generator'},'/reports/print/movements':{'Super User','Report Generator'},'/reports-v4/export':{'Super User','Report Generator'}}
@pytest.mark.parametrize('role',ACCOUNTS)
@pytest.mark.parametrize('path',PAGES)
def test_direct_page_permissions(app,path,role):
 assert role_client(app,role).get(path).status_code==(200 if role in PAGES[path] else 403)

@pytest.mark.parametrize('role,path,method',[
 (role,path,method)
 for role in ['Encoder','Report Generator','Employee']
 for path,method in [('/api/inventory/1','DELETE'),('/vendors/save','POST'),('/vendors/1/update','POST'),('/vendors/1/delete','POST'),('/users/create','POST'),('/users/1/toggle','POST'),('/requests/1/action','POST'),('/assignments/create','POST'),('/requisitions/create','POST'),('/inventory-audit/create','POST'),('/inventory-audit/1/assign','POST'),('/lifecycle/1/update','POST')]
 if not (role=='Encoder' and path in ('/assignments/create','/requisitions/create','/requests/1/action'))
])
def test_denied_mutations_with_valid_csrf(app,path,method,role):
 c=role_client(app,role)
 assert c.open(path,method=method,data={'_csrf':get_csrf_token(c)}).status_code==403

@pytest.mark.parametrize('role',['Report Generator','Employee'])
@pytest.mark.parametrize('path',['/api/movement','/api/inventory'])
def test_cannot_change_stock(app,app_module,role,path):
 c=role_client(app,role);before=app_module.get_item(1)['qty']
 assert c.post(path,json=dict(inventory_id=1,movement_type='in',quantity=999),headers={'X-CSRFToken':get_csrf_token(c)}).status_code==403
 assert app_module.get_item(1)['qty']==before

def test_every_protected_route_has_policy(app_module):
 assert {r.endpoint for r in app_module.app.url_map.iter_rules()}-{'login','logout','static','healthz'}-set(app_module.ENDPOINT_ROLES)==set()

def test_encoder_assigned_scope_draft_persistence_and_stale_version(app,hr_client,app_module):
 aid,rows=make_audit(hr_client,app_module);c=app_module.db();eid=c.execute("SELECT id FROM users WHERE role='Encoder'").fetchone()['id'];c.close();encoder=role_client(app,'Encoder')
 assert encoder.get(f'/inventory-audit/{aid}').status_code==403
 assert hr_client.post(f'/inventory-audit/{aid}/assign',data=dict(assigned_to=eid,_csrf=get_csrf_token(hr_client))).status_code==302
 assert encoder.get(f'/inventory-audit/{aid}').status_code==200
 r=rows[0];data={f"actual_{r['id']}":'2',f"notes_{r['id']}":'Partial check', 'audit_action':'draft','draft_revision':1,'_csrf':get_csrf_token(encoder)}
 response=encoder.post(f'/inventory-audit/{aid}',data=data,headers={'Accept':'application/json'})
 assert response.status_code==200 and response.json['revision']==2
 page=encoder.get(f'/inventory-audit/{aid}').text
 assert f'name="actual_{r["id"]}" value="2"' in page and 'Partial check' in page
 assert encoder.post(f'/inventory-audit/{aid}',data=data,headers={'Accept':'application/json'}).status_code==409
 data['draft_revision']=2;data[f"actual_{r['id']}"]='';data[f"notes_{r['id']}"]='Only notes so far'
 assert encoder.post(f'/inventory-audit/{aid}',data=data,headers={'Accept':'application/json'}).status_code==200
 c=app_module.db();saved=c.execute('SELECT draft_qty,draft_notes,actual_qty FROM inventory_audit_items WHERE id=?',(r['id'],)).fetchone();c.close()
 assert saved['draft_qty'] is None and saved['draft_notes']=='Only notes so far' and saved['actual_qty'] is None

def test_finalize_locks_audit(hr_client,app_module):
 aid,rows=make_audit(hr_client,app_module);data={f"actual_{r['id']}":r['expected_qty'] for r in rows};data.update(audit_action='finalize',draft_revision=0,_csrf=get_csrf_token(hr_client))
 result=hr_client.post(f'/inventory-audit/{aid}',data=data,headers={'Accept':'application/json'})
 assert result.status_code==200 and result.json['finalized']
 data['draft_revision']=1
 assert hr_client.post(f'/inventory-audit/{aid}',data=data,headers={'Accept':'application/json'}).status_code==409

def test_weekly_reports_keep_older_stock_and_legacy_department(hr_client,app_module):
 iid=create_item(hr_client,received_date=(date.today()-timedelta(days=80)).isoformat());c=app_module.db();c.execute('UPDATE inventory SET custodian=? WHERE id=?',('IT / Admin',iid));c.commit();c.close()
 for period in ['week','month']:
  records=list(csv.DictReader(io.StringIO(hr_client.get('/reports-v4/export',query_string=dict(period=period,department='IT / Admin')).text)))
  assert app_module.get_item(iid)['item_no'] in {r['Inventory Tag'] for r in records}
 page=hr_client.get('/reports-v4?period=week').text
 # The Figma-integrated Reports UI labels the reset action "Clear all".
 # Verify the actual reset destination and the accessible per-filter removal label.
 assert 'class="report-reset" href="/reports-v4">Clear all</a>' in page
 assert 'aria-label="Remove Reporting period filter"' in page

def test_default_acquisition_date_persisted(hr_client,app_module):
 iid=create_item(hr_client,received_date='');assert app_module.get_item(iid)['received_date']==date.today().isoformat()

def test_password_validation_hashing_session_revocation_and_no_role_change(app,app_module):
 c=app_module.db();email='settings'+secrets.token_hex(4)+'@example.com';c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',('Settings Tester',email,app_module.generate_password_hash('OldPassword123'),'Employee','Operations',app_module.now()));c.commit();uid=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()['id'];c.close()
 one,two=app.test_client(),app.test_client()
 for client in [one,two]:assert client.post('/login',data=dict(email=email,password='OldPassword123')).status_code==302
 data=dict(name='Updated Person',email=email,phone='09123456789',current_password='wrong',new_password='NewPassword456',confirm_password='NewPassword456',role='Super User',department='Admin',_csrf=get_csrf_token(one))
 assert one.post('/settings',data=data).status_code==400
 data['current_password']='OldPassword123';data['confirm_password']='Mismatch123';assert one.post('/settings',data=data).status_code==400
 data['confirm_password']='NewPassword456';assert one.post('/settings',data=data).status_code==302
 c=app_module.db();u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone();c.close()
 assert u['role']=='Employee' and u['department']=='Operations' and u['phone']=='09123456789'
 assert app_module.check_password_hash(u['password_hash'],'NewPassword456') and u['password_hash']!='NewPassword456'
 assert two.get('/settings').status_code==302 and one.get('/settings').status_code==200

def test_employee_dashboard_has_no_global_movement_history(app):
 result=role_client(app,'Employee').get('/api/dashboard').json;assert result['recent']==[] and result['value']==0

def test_migration_runs_twice_without_data_loss(app_module):
 app_module.init_db();app_module.init_db();c=app_module.db();cols={r['name'] for r in c.execute('PRAGMA table_info(inventory_audits)').fetchall()};c.close()
 assert {'assigned_to','draft_saved_at','draft_revision'}<=cols


def test_cleared_legacy_count_stays_empty_after_draft(hr_client,app_module):
 aid,rows=make_audit(hr_client,app_module);rid=rows[0]['id'];c=app_module.db();c.execute('UPDATE inventory_audit_items SET actual_qty=8 WHERE id=?',(rid,));c.commit();c.close()
 result=hr_client.post(f'/inventory-audit/{aid}',data={f'actual_{rid}':'','audit_action':'draft','draft_revision':0,'_csrf':get_csrf_token(hr_client)},headers={'Accept':'application/json'})
 assert result.status_code==200
 assert f'name="actual_{rid}" value=""' in hr_client.get(f'/inventory-audit/{aid}').text
 result=hr_client.post(f'/inventory-audit/{aid}',data={'audit_action':'draft','draft_revision':1,'_csrf':get_csrf_token(hr_client)},headers={'Accept':'application/json'})
 assert result.status_code==200
 c=app_module.db();assert c.execute('SELECT draft_qty FROM inventory_audit_items WHERE id=?',(rid,)).fetchone()['draft_qty'] is None;c.close()
