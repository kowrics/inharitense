"""Request handoff, stage permissions, atomic release, clean option labels."""
import pytest,re,secrets
from tests.conftest import get_csrf_token
from tests.test_refinements import create_item
from tests.test_v7 import role_client

def action(client,rid,act):
 return client.post(f'/requests/{rid}/action',data=dict(action=act,_csrf=get_csrf_token(client)))

def request(employee,iid):
 return employee.post('/requests/create',data=dict(inventory_id=iid,quantity=2,purpose='Work supplies',_csrf=get_csrf_token(employee)))

def test_request_routes_encoder_then_superuser_and_release_once(app,app_module,hr_client):
 employee=role_client(app,'Employee');encoder=role_client(app,'Encoder');iid=create_item(hr_client,qty=10)
 c=app_module.db();start=c.execute('SELECT COALESCE(MAX(id),0) n FROM notifications').fetchone()['n'];c.close()
 assert request(employee,iid).status_code==302
 c=app_module.db();r=c.execute('SELECT * FROM requests WHERE inventory_id=? ORDER BY id DESC',(iid,)).fetchone();notices=c.execute('SELECT * FROM notifications WHERE id>?',(start,)).fetchall();c.close();rid=r['id']
 assert r['status']=='For Review' and any(n['recipient_role']=='Encoder' for n in notices) and not any(n['recipient_role']=='Super User' for n in notices)
 assert action(hr_client,rid,'approve').status_code==403
 assert action(encoder,rid,'fulfill').status_code==403
 assert action(encoder,rid,'approve').status_code==403
 assert action(encoder,rid,'endorse').status_code==302
 assert action(encoder,rid,'fulfill').status_code==403
 assert action(hr_client,rid,'approve').status_code==302
 c=app_module.db();approved=c.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();c.close()
 assert action(encoder,rid,'fulfill').status_code==302
 c=app_module.db();released=c.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();moves=c.execute("SELECT * FROM movements WHERE inventory_id=? AND movement_type='out'",(iid,)).fetchall();c.close()
 assert released['status']=='Fulfilled' and released['hr_by']==approved['hr_by'] and released['hr_at']==approved['hr_at']
 assert app_module.get_item(iid)['qty']==8 and app_module.get_item(iid)['times_out']==2 and len(moves)==1
 assert action(encoder,rid,'fulfill').status_code==403 and app_module.get_item(iid)['qty']==8
 assert 'Fulfilled' in employee.get('/requests').text

def test_encoder_can_reject_review_but_not_superuser_approval(app,app_module,hr_client):
 employee=role_client(app,'Employee');encoder=role_client(app,'Encoder');iid=create_item(hr_client,qty=10);assert request(employee,iid).status_code==302
 c=app_module.db();rid=c.execute('SELECT id FROM requests WHERE inventory_id=? ORDER BY id DESC',(iid,)).fetchone()['id'];c.close()
 assert action(encoder,rid,'reject_purchasing').status_code==302
 c=app_module.db();assert c.execute('SELECT status FROM requests WHERE id=?',(rid,)).fetchone()['status']=='Rejected by Encoder';c.close()
 assert app_module.get_item(iid)['qty']==10 and action(encoder,rid,'approve').status_code==403

@pytest.mark.parametrize('role,paths',[('Employee',['/requests']),('Encoder',['/requests','/assignments','/requisitions','/inventory'])])
def test_stock_counts_removed_from_item_options(app,role,paths):
 c=role_client(app,role)
 for path in paths:
  page=c.get(path);assert page.status_code==200
  options=re.findall(r'<option\b[^>]*>(.*?)</option>',page.text,re.S)
  assert not any(re.search(r'\b(?:available|on hand)\b',o,re.I) for o in options)
  if path!='/inventory':assert not any(re.search(r'\(\d+ available\)',o) for o in options)

def test_readonly_roles_cannot_act_on_requests(app):
 for role in ['Employee','Report Generator']:
  c=role_client(app,role)
  for a in ['endorse','approve','fulfill','note']:
   assert action(c,1,a).status_code==403

def test_concurrent_encoder_release_deducts_stock_once(app,app_module,hr_client):
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 iid=create_item(hr_client,qty=10);c=app_module.db();uid=c.execute("SELECT id FROM users WHERE role='Employee'").fetchone()['id'];no='REQ-RACE-'+secrets.token_hex(5)
 c.execute('INSERT INTO requests(request_no,inventory_id,quantity,requester_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(no,iid,2,uid,'Approved',app_module.now(),app_module.now()));c.commit();rid=c.execute('SELECT id FROM requests WHERE request_no=?',(no,)).fetchone()['id'];c.close()
 clients=[role_client(app,'Encoder') for _ in range(2)];barrier=Barrier(2)
 def release(client):barrier.wait();return action(client,rid,'fulfill').status_code
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(release,clients))
 assert sorted(results)==[302,403] and app_module.get_item(iid)['qty']==8
 c=app_module.db();assert c.execute("SELECT COUNT(*) n FROM movements WHERE inventory_id=? AND movement_type='out'",(iid,)).fetchone()['n']==1;c.close()
