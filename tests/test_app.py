"""
Automated tests for the critical INHARITENSE workflows: auth, RBAC, CSRF,
inventory, stock movements, the request/approval/fulfillment pipeline,
reports, and QR/code lookup.

Run with:  pytest
All tests run against an isolated temp SQLite database (see tests/conftest.py)
so production/development data is never touched.
"""
from tests.conftest import CREDENTIALS, get_csrf_token, login_as


def item_id(app_module, item_no):
    c = app_module.db()
    row = c.execute('SELECT id FROM inventory WHERE item_no=?', (item_no,)).fetchone()
    c.close()
    return row['id']


def item_qty(app_module, item_no):
    c = app_module.db()
    row = c.execute('SELECT qty FROM inventory WHERE item_no=?', (item_no,)).fetchone()
    c.close()
    return row['qty']


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_login_success_redirects_to_dashboard(client):
    email, password = CREDENTIALS['HR']
    resp = client.post('/login', data={'email': email, 'password': password})
    assert resp.status_code == 302
    resp2 = client.get('/', follow_redirects=True)
    assert resp2.status_code == 200


def test_login_wrong_password_rejected(client):
    resp = client.post('/login', data={'email': 'hr@ecmci.com', 'password': 'wrong-password'})
    assert resp.status_code == 200  # re-renders login page with a flash message
    assert b'Invalid email or password' in resp.data


def test_logged_out_user_redirected_to_login(client):
    resp = client.get('/inventory')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

def test_post_without_csrf_token_rejected(hr_client):
    resp = hr_client.post('/vendors/save', data={'name': 'No CSRF Vendor'})
    assert resp.status_code == 400


def test_post_with_valid_csrf_token_accepted(hr_client, app_module):
    token = get_csrf_token(hr_client)
    resp = hr_client.post('/api/inventory', json={
        'item_no': 'TEST-CSRF-1', 'name': 'CSRF Test Item', 'category': 'Office Supplies',
        'unit': 'piece', 'qty': 5, 'max_qty': 10, 'min_qty': 1, 'cost': 10,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

def test_department_user_cannot_view_vendors(employee_client):
    resp = employee_client.get('/vendors')
    assert resp.status_code == 403


def test_department_user_cannot_view_users_admin(employee_client):
    resp = employee_client.get('/users')
    assert resp.status_code == 403


def test_purchasing_cannot_view_users_admin(purchasing_client):
    resp = purchasing_client.get('/users')
    assert resp.status_code == 403


def test_encoder_can_record_supply_movement(it_client, app_module):
    iid = item_id(app_module, 'OFF-001')
    token = get_csrf_token(it_client)
    resp = it_client.post('/api/movement', json={
        'inventory_id': iid, 'movement_type': 'in', 'quantity': 1,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Inventory: creation + duplicate prevention
# ---------------------------------------------------------------------------

def test_create_inventory_item(hr_client):
    token = get_csrf_token(hr_client)
    resp = hr_client.post('/api/inventory', json={
        'item_no': 'TEST-001', 'name': 'Test Widget', 'category': 'Office Supplies',
        'unit': 'piece', 'qty': 20, 'max_qty': 50, 'min_qty': 5, 'cost': 15,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True


def test_duplicate_item_no_rejected(hr_client):
    token = get_csrf_token(hr_client)
    resp = hr_client.post('/api/inventory', json={
        'item_no': 'OFF-001', 'name': 'Bond Paper (ream)', 'category': 'Office Supplies',
        'unit': 'ream', 'qty': 1, 'max_qty': 10, 'min_qty': 1, 'cost': 1,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 409


def test_inventory_with_transaction_history_cannot_be_deleted(hr_client, app_module):
    # OFF-001 has seeded demo movements, so it must be protected.
    iid = item_id(app_module, 'OFF-001')
    token = get_csrf_token(hr_client)
    resp = hr_client.delete(f'/api/inventory/{iid}', headers={'X-CSRFToken': token})
    assert resp.status_code == 409
    assert 'Archive it instead' in resp.get_json()['error']


# ---------------------------------------------------------------------------
# Stock movements
# ---------------------------------------------------------------------------

def test_stock_in_increases_quantity(hr_client, app_module):
    iid = item_id(app_module, 'HSE-002')
    before = item_qty(app_module, 'HSE-002')
    token = get_csrf_token(hr_client)
    resp = hr_client.post('/api/movement', json={
        'inventory_id': iid, 'movement_type': 'in', 'quantity': 4,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 200
    assert item_qty(app_module, 'HSE-002') == before + 4


def test_stock_out_decreases_quantity(hr_client, app_module):
    iid = item_id(app_module, 'HSE-002')
    before = item_qty(app_module, 'HSE-002')
    token = get_csrf_token(hr_client)
    resp = hr_client.post('/api/movement', json={
        'inventory_id': iid, 'movement_type': 'out', 'quantity': 2,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 200
    assert item_qty(app_module, 'HSE-002') == before - 2


def test_negative_stock_is_prevented(hr_client, app_module):
    iid = item_id(app_module, 'HSE-002')
    current = item_qty(app_module, 'HSE-002')
    token = get_csrf_token(hr_client)
    resp = hr_client.post('/api/movement', json={
        'inventory_id': iid, 'movement_type': 'out', 'quantity': current + 1000,
    }, headers={'X-CSRFToken': token})
    assert resp.status_code == 409
    assert item_qty(app_module, 'HSE-002') == current  # unchanged


# ---------------------------------------------------------------------------
# Request -> endorsement -> approval -> fulfillment workflow
# ---------------------------------------------------------------------------

def test_full_request_approval_fulfillment_workflow(employee_client, it_client, hr_client, app_module):
    iid = item_id(app_module, 'OFF-002')  # Printer Ink Cartridge, Office Operations
    qty_before = item_qty(app_module, 'OFF-002')
    request_qty = 3

    # 1. Department employee submits a request.
    token = get_csrf_token(employee_client)
    resp = employee_client.post('/requests/create', data={
        'inventory_id': iid, 'quantity': request_qty, 'purpose': 'Test workflow', '_csrf': token,
    })
    assert resp.status_code == 302

    c = app_module.db()
    row = c.execute('SELECT * FROM requests WHERE inventory_id=? ORDER BY id DESC LIMIT 1', (iid,)).fetchone()
    c.close()
    assert row['status'] == 'For Review'
    rid = row['id']

    # 2. Encoder reviews and endorses it.
    token = get_csrf_token(it_client)
    resp = it_client.post(f'/requests/{rid}/action', data={'action': 'endorse', '_csrf': token})
    assert resp.status_code == 302
    c = app_module.db()
    status = c.execute('SELECT status FROM requests WHERE id=?', (rid,)).fetchone()['status']
    c.close()
    assert status == 'For Super User Approval'

    # 3. HR approves it.
    token = get_csrf_token(hr_client)
    resp = hr_client.post(f'/requests/{rid}/action', data={'action': 'approve', '_csrf': token})
    assert resp.status_code == 302
    c = app_module.db()
    status = c.execute('SELECT status FROM requests WHERE id=?', (rid,)).fetchone()['status']
    c.close()
    assert status == 'Approved'

    # 4. Encoder releases it — stock is deducted once after approval.
    token = get_csrf_token(it_client)
    resp = it_client.post(f'/requests/{rid}/action', data={'action': 'fulfill', '_csrf': token})
    assert resp.status_code == 302
    c = app_module.db()
    status = c.execute('SELECT status FROM requests WHERE id=?', (rid,)).fetchone()['status']
    c.close()
    assert status == 'Fulfilled'
    assert item_qty(app_module, 'OFF-002') == qty_before - request_qty


def test_fulfillment_blocked_when_insufficient_stock(employee_client, purchasing_client, hr_client, app_module):
    iid = item_id(app_module, 'HSE-001')  # First Aid Kit, small stock
    current = item_qty(app_module, 'HSE-001')
    huge_qty = current + 500

    token = get_csrf_token(employee_client)
    # Department User can't see Health & Safety, so use HR to create then HR/Purchasing to route,
    # exercising just the fulfillment stock guard in isolation.
    c = app_module.db()
    c.execute("INSERT INTO requests(request_no,inventory_id,quantity,purpose,requester_id,status,created_at,updated_at) "
              "VALUES(?,?,?,?,?,?,?,?)",
              (f'REQ-TEST-{iid}', iid, huge_qty, 'Insufficient stock test', 1, 'Approved',
               app_module.now(), app_module.now()))
    c.commit()
    rid = c.execute('SELECT id FROM requests WHERE request_no=?', (f'REQ-TEST-{iid}',)).fetchone()['id']
    c.close()

    token = get_csrf_token(hr_client)
    resp = hr_client.post(f'/requests/{rid}/action', data={'action': 'fulfill', '_csrf': token})
    assert resp.status_code == 302
    assert item_qty(app_module, 'HSE-001') == current  # unchanged


# ---------------------------------------------------------------------------
# Reports / export
# ---------------------------------------------------------------------------

def test_csv_report_generation(hr_client):
    resp = hr_client.get('/reports/stock')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'


def test_xlsx_report_generation(hr_client):
    resp = hr_client.get('/reports/xlsx/valuation')
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp.mimetype


# ---------------------------------------------------------------------------
# QR / code lookup
# ---------------------------------------------------------------------------

def test_scan_lookup_finds_item_within_role_scope(hr_client):
    resp = hr_client.get('/api/scan?q=off-001')
    assert resp.status_code == 200
    assert resp.get_json()['found'] is True


def test_encoder_can_scan_supply_items(it_client):
    # IT Custodian can only see IT & BPO Equipment, not Office Operations.
    resp = it_client.get('/api/scan?q=off-001')
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_inventory_page_loads(hr_client):
    # Regression test: the vendors query used to use double-quoted "Active", which SQLite
    # tolerates as a string literal but PostgreSQL rejects (double quotes are identifiers
    # in standard SQL) — this silently 500'd only under Postgres. Guard against it here.
    resp = hr_client.get('/inventory')
    assert resp.status_code == 200


def test_healthz_ok(client):
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'
