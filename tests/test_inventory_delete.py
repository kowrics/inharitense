"""Regression tests: Super User-only deletion, audit snapshots and retained history."""
import json
import secrets
from datetime import datetime
from tests.conftest import get_csrf_token


def new_item(module):
    c = module.db()
    suffix = secrets.token_hex(5).upper()
    cur = c.execute('''INSERT INTO inventory
        (item_no,code,name,category,unit,qty,max_qty,min_qty,cost,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''',
        (f'DEL-{suffix}', f'DEL-CODE-{suffix}', f'Delete QA {suffix}',
         'Office Equipment', 'piece', 0, 10, 0, 0, datetime.now().isoformat(timespec='seconds')))
    iid = cur.lastrowid
    c.commit()
    c.close()
    return iid


def remove(client, iid, reason='Duplicate record entered during encoding'):
    return client.delete(f'/api/inventory/{iid}',
                         json={'reason': reason},
                         headers={'X-CSRFToken': get_csrf_token(client)})


def test_superuser_unlinked_deletion_creates_audit_snapshot(hr_client, app_module):
    iid = new_item(app_module)
    response = remove(hr_client, iid)
    assert response.status_code == 200
    assert response.json['removal_type'] == 'permanent'
    c = app_module.db()
    assert c.execute('SELECT id FROM inventory WHERE id=?', (iid,)).fetchone() is None
    log = c.execute('SELECT * FROM inventory_deletion_logs WHERE inventory_id=?', (iid,)).fetchone()
    assert log and log['reason'] == 'Duplicate record entered during encoding'
    assert json.loads(log['item_snapshot'])['id'] == iid
    assert c.execute('SELECT 1 FROM audit_logs WHERE user_id=? AND item_no=?',
                     (log['deleted_by'], log['item_no'])).fetchone()
    c.close()


def test_superuser_linked_history_is_retained(hr_client, app_module):
    iid = new_item(app_module)
    c = app_module.db()
    user_id = c.execute("SELECT id FROM users WHERE email='admin@ecmci.com'").fetchone()['id']
    c.execute('INSERT INTO movements(inventory_id,movement_type,quantity,note,by_user,created_at) VALUES(?,?,?,?,?,?)',
              (iid, 'in', 5, 'Stock IN test', user_id, datetime.now().isoformat(timespec='seconds')))
    c.commit()
    c.close()
    response = remove(hr_client, iid)
    assert response.status_code == 200
    assert response.json['removal_type'] == 'history_retained'
    c = app_module.db()
    item = c.execute('SELECT * FROM inventory WHERE id=?', (iid,)).fetchone()
    assert item['deleted_at'] is not None and item['deleted_by'] == user_id
    assert c.execute('SELECT COUNT(*) AS n FROM movements WHERE inventory_id=?', (iid,)).fetchone()['n'] == 1
    c.close()
    assert app_module.get_item(iid) is None
    assert f'id="inventory-{iid}"' not in hr_client.get('/inventory').get_data(as_text=True)


def test_deletion_reason_is_required(hr_client, app_module):
    iid = new_item(app_module)
    response = remove(hr_client, iid, 'short')
    assert response.status_code == 400
    c = app_module.db()
    assert c.execute('SELECT 1 FROM inventory WHERE id=?', (iid,)).fetchone()
    assert c.execute('SELECT 1 FROM inventory_deletion_logs WHERE inventory_id=?', (iid,)).fetchone() is None
    c.close()


def test_non_super_user_cannot_delete(it_client, app_module):
    iid = new_item(app_module)
    response = remove(it_client, iid)
    assert response.status_code == 403
    c = app_module.db()
    assert c.execute('SELECT 1 FROM inventory WHERE id=?', (iid,)).fetchone()
    c.close()
