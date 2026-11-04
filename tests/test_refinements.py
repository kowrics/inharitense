"""Regression checks for inventory consistency and finalized records."""
import csv
import io
import secrets
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from tests.conftest import get_csrf_token, login_as


def create_item(client, **overrides):
    data=dict(name='Regression '+secrets.token_hex(5),category='Office Supplies',unit='piece',qty=10,min_qty=1,max_qty=20,cost=5,received_date=date.today().isoformat())
    data.update(overrides)
    response=client.post('/api/inventory',json=data,headers={'X-CSRFToken':get_csrf_token(client)})
    assert response.status_code==200,response.data
    return response.json['id']


def test_opening_stock_recorded(hr_client,app_module):
    iid=create_item(hr_client)
    c=app_module.db();r=c.execute('SELECT * FROM movements WHERE inventory_id=?',(iid,)).fetchone();c.close()
    assert r['quantity']==10 and r['movement_type']=='in' and r['note']=='Opening stock'


def test_edit_cannot_rewrite_stock(hr_client,app_module):
    iid=create_item(hr_client);data=dict(app_module.get_item(iid));data['qty']=500
    response=hr_client.post('/api/inventory',json=data,headers={'X-CSRFToken':get_csrf_token(hr_client)})
    assert response.status_code==409 and app_module.get_item(iid)['qty']==10
    data['qty']=10;data['cost']=99
    assert hr_client.post('/api/inventory',json=data,headers={'X-CSRFToken':get_csrf_token(hr_client)}).status_code==200
    assert app_module.get_item(iid)['cost']==99


def test_invalid_movement_rejected(hr_client,app_module):
    iid=create_item(hr_client)
    for qty in [0,-1,'abc']:
        r=hr_client.post('/api/movement',json=dict(inventory_id=iid,movement_type='out',quantity=qty),headers={'X-CSRFToken':get_csrf_token(hr_client)})
        assert r.status_code==400
    assert app_module.get_item(iid)['qty']==10


def test_simultaneous_assignments_cannot_overdraw(app,hr_client,app_module):
    iid=create_item(hr_client,qty=1)
    c=app_module.db();eid=c.execute("SELECT id FROM users WHERE role='Employee'").fetchone()['id'];c.close()
    clients=[app.test_client(),app.test_client()]
    for client in clients:login_as(client,'HR')
    def assign(client):
        return client.post('/assignments/create',data=dict(inventory_id=iid,employee_id=eid,quantity=1,_csrf=get_csrf_token(client))).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(assign,clients))==[302,302]
    c=app_module.db();assert c.execute('SELECT COUNT(*) n FROM assignments WHERE inventory_id=?',(iid,)).fetchone()['n']==1;c.close()
    assert app_module.get_item(iid)['qty']==0


def test_assignment_requires_active_employee(hr_client,app_module):
    iid=create_item(hr_client);c=app_module.db();uid=c.execute("SELECT id FROM users WHERE role='Super User'").fetchone()['id'];c.close()
    r=hr_client.post('/assignments/create',data=dict(inventory_id=iid,employee_id=uid,quantity=1,_csrf=get_csrf_token(hr_client)))
    assert r.status_code==400 and app_module.get_item(iid)['qty']==10


def make_audit(client,app_module):
    r=client.post('/inventory-audit/create',data=dict(title='Regression Audit',category='Office Supplies',_csrf=get_csrf_token(client)))
    assert r.status_code==302
    aid=int(r.location.rsplit('/',1)[1]);c=app_module.db();rows=c.execute('SELECT * FROM inventory_audit_items WHERE audit_id=?',(aid,)).fetchall();c.close()
    return aid,rows


def test_finalized_audit_locked(hr_client,app_module):
    aid,rows=make_audit(hr_client,app_module)
    data={f"actual_{r['id']}":r['expected_qty'] for r in rows};data.update(_csrf=get_csrf_token(hr_client),finalize='1',draft_revision='0')
    assert hr_client.post(f'/inventory-audit/{aid}',data=data).status_code==302
    data[f"actual_{rows[0]['id']}"]=0
    assert hr_client.post(f'/inventory-audit/{aid}',data=data).status_code==409
    c=app_module.db();assert c.execute('SELECT actual_qty FROM inventory_audit_items WHERE id=?',(rows[0]['id'],)).fetchone()['actual_qty']==rows[0]['expected_qty'];c.close()


def test_audit_draft_allows_partial_counts_and_finalization_requires_notes(hr_client,app_module):
    aid,rows=make_audit(hr_client,app_module)
    assert hr_client.post(f'/inventory-audit/{aid}',data=dict(_csrf=get_csrf_token(hr_client),finalize=1,draft_revision=0)).status_code==400
    r=rows[0]
    assert hr_client.post(f'/inventory-audit/{aid}',data={f"actual_{r['id']}":r['expected_qty']+1,'_csrf':get_csrf_token(hr_client),'draft_revision':0}).status_code==302
    c=app_module.db();saved=c.execute('SELECT * FROM inventory_audit_items WHERE id=?',(r['id'],)).fetchone();c.close()
    assert saved['draft_qty']==r['expected_qty']+1 and saved['actual_qty'] is None
    assert hr_client.get('/inventory-audit/999999').status_code==404


def test_report_export_matches_period_and_preview(hr_client,app_module):
    iid=create_item(hr_client);old=create_item(hr_client,received_date=(date.today()-timedelta(days=80)).isoformat())
    for period in ['week','month']:
        url=f'/reports-v4?period={period}&start={date.today().isoformat()}';page=hr_client.get(url)
        export=hr_client.get(f'/reports-v4/export?period={period}&start={date.today().isoformat()}')
        records=list(csv.DictReader(io.StringIO(export.text)))
        tag=app_module.get_item(iid)['item_no'];oldtag=app_module.get_item(old)['item_no']
        assert tag in page.text and oldtag not in page.text
        assert tag in {r['Inventory Tag'] for r in records} and oldtag not in {r['Inventory Tag'] for r in records}
        with app_module.app.test_request_context(url):rows,_,_=app_module.inventory_report_data()
        assert [(r['item_no'],r['assignment_department']) for r in rows]==[(r['Inventory Tag'],r['Assigned Department / Custody']) for r in records]


def test_forecast_uses_complete_weeks_and_insufficient_data(hr_client,app_module):
    iid=create_item(hr_client);item=app_module.get_item(iid)
    assert app_module.forecast_for(item)['data_status']=='Insufficient historical usage'
    monday=date.today()-timedelta(days=date.today().weekday());c=app_module.db();uid=c.execute("SELECT id FROM users WHERE role='Super User'").fetchone()['id']
    for w in range(1,27):c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(iid,'out',7,'Test',uid,(monday-timedelta(weeks=w)).isoformat()+'T12:00:00'))
    c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',(iid,'out',999,'Partial week',uid,monday.isoformat()+'T12:00:00'));c.commit();c.close()
    f=app_module.forecast_for(item)
    assert f['history_weeks']==[7]*26 and f['predicted_weekly']==7 and f['daily']==1


def test_restart_preserves_account_changes(app_module):
    c=app_module.db();c.execute("UPDATE users SET name='Custom Administrator',password_hash='sentinel' WHERE email='admin@ecmci.com'");c.commit();c.close()
    app_module.init_db()
    c=app_module.db();r=c.execute("SELECT name,password_hash FROM users WHERE email='admin@ecmci.com'").fetchone();c.close()
    assert tuple(r)==('Custom Administrator','sentinel')
    # Restore so later tests remain independent of this password change.
    c=app_module.db();c.execute("UPDATE users SET password_hash=? WHERE email='admin@ecmci.com'",(app_module.generate_password_hash('admin123'),));c.commit();c.close()
