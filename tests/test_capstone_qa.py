"""Focused acceptance checks for the remaining capstone QA requirements.

These tests use the existing isolated SQLite test fixture and seeded demo roles.
They intentionally exercise user-visible Flask routes instead of a production service
stack, which is the expected capstone demonstration environment.
"""
import csv
import io
import re
import secrets
from datetime import date
from pathlib import Path

from tests.conftest import get_csrf_token
from tests.test_refinements import create_item
from tests.test_v7 import role_client


def _csrf(client):
    return {'X-CSRFToken': get_csrf_token(client)}


def _new_user(app_module, role, password='CapstoneQA123'):
    email = f"capstone-{secrets.token_hex(5)}@example.com"
    conn = app_module.db()
    conn.execute(
        'INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
        ('Capstone QA User', email, app_module.generate_password_hash(password), role, 'QA', app_module.now()),
    )
    conn.commit()
    conn.close()
    return email, password


def test_notification_read_status_is_per_account_and_panel_get_does_not_mark(app, app_module, monkeypatch):
    monkeypatch.setattr(app_module, 'send_email', lambda *args, **kwargs: None)
    first = role_client(app, 'Encoder')
    second_email, second_password = _new_user(app_module, 'Encoder')
    second = app.test_client()
    assert second.post('/login', data={'email': second_email, 'password': second_password}).status_code == 302

    conn = app_module.db()
    app_module.notify('Encoder', 'QA shared-role notification', 'Account-specific read test.', conn=conn)
    conn.commit()
    notification = conn.execute(
        "SELECT id FROM notifications WHERE title='QA shared-role notification' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    notification_id = notification['id']
    conn.close()

    # Fetching/opening the panel must not mark the notification as read.
    first_payload = first.get('/api/notifications').json
    second_payload = second.get('/api/notifications').json
    assert first_payload['unread_count'] >= 1 and second_payload['unread_count'] >= 1
    first_item = next(row for row in first_payload['items'] if row['id'] == notification_id)
    second_item = next(row for row in second_payload['items'] if row['id'] == notification_id)
    assert first_item['read_flag'] == 0 and second_item['read_flag'] == 0

    marked = first.post(f'/api/notifications/{notification_id}/read', headers=_csrf(first))
    assert marked.status_code == 200
    first_after = first.get('/api/notifications').json
    second_after = second.get('/api/notifications').json
    assert next(row for row in first_after['items'] if row['id'] == notification_id)['read_flag'] == 1
    assert next(row for row in second_after['items'] if row['id'] == notification_id)['read_flag'] == 0

    # Mark All as Read is also scoped to the acting account.
    assert first.post('/api/notifications/read', headers=_csrf(first)).status_code == 200
    second_after_all = second.get('/api/notifications').json
    assert next(row for row in second_after_all['items'] if row['id'] == notification_id)['read_flag'] == 0


def test_low_stock_notification_triggers_only_when_crossing_threshold(app_module, hr_client, it_client, monkeypatch):
    sent = []
    monkeypatch.setattr(app_module, 'send_email', lambda recipients, subject, message: sent.append((list(recipients), subject, message)))
    item_id = create_item(hr_client, qty=10, min_qty=5, max_qty=20)
    movement = it_client.post('/api/movement', json={
        'inventory_id': item_id, 'movement_type': 'out', 'quantity': 6, 'note': 'QA threshold test'
    }, headers=_csrf(it_client))
    assert movement.status_code == 200
    assert app_module.get_item(item_id)['qty'] == 4

    conn = app_module.db()
    item_no = app_module.get_item(item_id)['item_no']
    alerts = conn.execute("SELECT * FROM notifications WHERE kind='low_stock' AND message LIKE ?", (f'%{item_no}%',)).fetchall()
    conn.close()
    assert len(alerts) == 3  # Super User, Admin, Inventory Manager recipient groups.
    assert len(sent) == 3

    # Further reductions while already below the threshold do not spam duplicate alerts.
    second_move = it_client.post('/api/movement', json={
        'inventory_id': item_id, 'movement_type': 'out', 'quantity': 1
    }, headers=_csrf(it_client))
    assert second_move.status_code == 200
    conn = app_module.db()
    repeated = conn.execute("SELECT COUNT(*) n FROM notifications WHERE kind='low_stock' AND message LIKE ?", (f'%{item_no}%',)).fetchone()['n']
    conn.close()
    assert repeated == 3


def test_zero_minimum_stock_still_generates_out_of_stock_alert(app_module, hr_client, it_client, monkeypatch):
    monkeypatch.setattr(app_module, 'send_email', lambda *args, **kwargs: None)
    item_id = create_item(hr_client, qty=1, min_qty=0, max_qty=10)
    response = it_client.post('/api/movement', json={
        'inventory_id': item_id, 'movement_type': 'out', 'quantity': 1
    }, headers=_csrf(it_client))
    assert response.status_code == 200
    conn = app_module.db()
    item_no = app_module.get_item(item_id)['item_no']
    row = conn.execute("SELECT COUNT(*) n FROM notifications WHERE kind='low_stock' AND title='Out of stock' AND message LIKE ?", (f'%{item_no}%',)).fetchone()
    conn.close()
    assert row['n'] == 3


def test_request_submission_rate_limit_returns_429_and_does_not_create_sixth_request(app, app_module, hr_client):
    item_id = create_item(hr_client)
    email, password = _new_user(app_module, 'Employee')
    employee = app.test_client()
    assert employee.post('/login', data={'email': email, 'password': password}).status_code == 302
    statuses = []
    for _ in range(6):
        response = employee.post('/requests/create', data={
            'inventory_id': item_id, 'quantity': '1', 'purpose': 'Capstone QA test',
            '_csrf': get_csrf_token(employee),
        })
        statuses.append(response.status_code)
    assert statuses[:5] == [302] * 5
    assert statuses[5] == 429
    assert employee.post('/requests/create', data={
        'inventory_id': item_id, 'quantity': '1', 'purpose': 'Capstone QA retry',
        '_csrf': get_csrf_token(employee),
    }).headers.get('Retry-After') == '60'
    conn = app_module.db()
    count = conn.execute('SELECT COUNT(*) n FROM requests WHERE requester_id=(SELECT id FROM users WHERE email=?)', (email,)).fetchone()['n']
    conn.close()
    assert count == 5


def test_duplicate_inventory_attempt_creates_alert_and_returns_conflict(app_module, hr_client, it_client, monkeypatch):
    monkeypatch.setattr(app_module, 'send_email', lambda *args, **kwargs: None)
    item_id = create_item(hr_client)
    item = app_module.get_item(item_id)
    response = it_client.post('/api/inventory', json={
        'name': item['name'], 'category': item['category'], 'unit': item['unit'],
        'qty': 0, 'min_qty': 0, 'max_qty': 10, 'cost': 1,
        'received_date': date.today().isoformat(),
    }, headers=_csrf(it_client))
    assert response.status_code == 409
    conn = app_module.db()
    item_name = item['name']
    alerts = conn.execute("SELECT COUNT(*) n FROM notifications WHERE kind='duplicate' AND message LIKE ?", (f'%{item_name}%',)).fetchone()['n']
    conn.close()
    assert alerts == 3


def test_inventory_image_upload_and_update_preserves_existing_image(hr_client, app_module):
    import base64
    image_bytes = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jv8sAAAAASUVORK5CYII=')
    response = hr_client.post('/api/inventory', data={
        'name': 'Image QA ' + secrets.token_hex(4), 'category': 'Office Equipment', 'unit': 'piece',
        'qty': '2', 'min_qty': '1', 'max_qty': '5', 'cost': '10',
        'received_date': date.today().isoformat(),
        'image': (io.BytesIO(image_bytes), 'item.png'),
    }, content_type='multipart/form-data', headers=_csrf(hr_client))
    assert response.status_code == 200, response.data
    item_id = response.json['id']
    item = app_module.get_item(item_id)
    assert item['image_path'].startswith('uploads/inventory/')
    image_path = app_module.BASE_DIR / 'static' / item['image_path']
    assert image_path.is_file() and image_path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')

    update = hr_client.post('/api/inventory', data={
        'id': str(item_id), 'item_no': item['item_no'], 'code': item['code'], 'name': item['name'],
        'category': item['category'], 'unit': item['unit'], 'qty': str(item['qty']),
        'min_qty': str(item['min_qty']), 'max_qty': str(item['max_qty']), 'cost': '12',
        'received_date': item['received_date'] or date.today().isoformat(),
    }, content_type='multipart/form-data', headers=_csrf(hr_client))
    assert update.status_code == 200, update.data
    assert app_module.get_item(item_id)['image_path'] == item['image_path']
    image_path.unlink(missing_ok=True)


def test_bulk_import_preview_confirm_creates_stock_movement_and_batch(app, app_module):
    encoder = role_client(app, 'Encoder')
    name = 'Bulk QA ' + secrets.token_hex(4)
    csv_data = (
        'item_no,code,name,category,unit,qty,max_qty,min_qty,cost,received_date\n'
        f',,{name},Office Supplies,piece,3,10,1,12.50,{date.today().isoformat()}\n'
    ).encode('utf-8')
    preview = encoder.post('/inventory/import/preview', data={
        '_csrf': get_csrf_token(encoder), 'upload': (io.BytesIO(csv_data), 'qa-import.csv')
    }, content_type='multipart/form-data')
    assert preview.status_code == 200
    assert b'All 1 rows passed validation' in preview.data
    batch_match = re.search(rb'name="batch_id" value="([^"]+)"', preview.data)
    assert batch_match
    batch_id = batch_match.group(1).decode()
    completed = encoder.post('/inventory/import/confirm', data={
        '_csrf': get_csrf_token(encoder), 'batch_id': batch_id,
    })
    assert completed.status_code == 302
    conn = app_module.db()
    item = conn.execute('SELECT * FROM inventory WHERE name=?', (name,)).fetchone()
    assert item and item['qty'] == 3
    movement = conn.execute("SELECT * FROM movements WHERE inventory_id=? AND note='Bulk import opening stock'", (item['id'],)).fetchone()
    batch = conn.execute('SELECT status FROM inventory_import_batches WHERE batch_id=?', (batch_id,)).fetchone()
    conn.close()
    assert movement and movement['quantity'] == 3 and batch['status'] == 'Imported'


def test_bulk_import_rejects_fractional_quantity_without_importing(app, app_module):
    encoder = role_client(app, 'Encoder')
    name = 'Invalid bulk QA ' + secrets.token_hex(4)
    csv_data = (
        'name,category,unit,qty,max_qty,min_qty,cost,received_date\n'
        f'{name},Office Supplies,piece,2.5,10,1,1,{date.today().isoformat()}\n'
    ).encode('utf-8')
    response = encoder.post('/inventory/import/preview', data={
        '_csrf': get_csrf_token(encoder), 'upload': (io.BytesIO(csv_data), 'invalid.csv')
    }, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'whole numbers' in response.data
    assert b'Confirm Import' not in response.data
    conn = app_module.db()
    found = conn.execute('SELECT id FROM inventory WHERE name=?', (name,)).fetchone()
    conn.close()
    assert found is None


def test_transfer_confirmation_and_maintenance_recorder_are_visible(app, app_module, hr_client):
    encoder = role_client(app, 'Encoder')
    item_id = create_item(hr_client)
    transfer_response = encoder.post('/asset-operations/transfer', data={
        '_csrf': get_csrf_token(encoder), 'inventory_id': str(item_id), 'quantity': '1',
        'from_department': 'IT / Admin', 'to_department': 'Operations', 'kind': 'Transfer',
        'notes': 'QA transfer confirmation',
    })
    assert transfer_response.status_code == 302
    conn = app_module.db()
    transfer = conn.execute("SELECT * FROM asset_transfers WHERE notes='QA transfer confirmation' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert transfer
    confirmed = hr_client.post(f"/asset-operations/transfer/{transfer['id']}/complete", data={'_csrf': get_csrf_token(hr_client)})
    assert confirmed.status_code == 302
    circulation_page = encoder.get('/asset-operations?view=circulation')
    assert circulation_page.status_code == 200
    assert b'Confirmed By / At' in circulation_page.data
    assert b'System Administrator' in circulation_page.data

    maintenance = encoder.post('/asset-operations/maintenance', data={
        '_csrf': get_csrf_token(encoder), 'inventory_id': str(item_id), 'kind': 'Inspection',
        'condition_after': 'Good', 'performed_on': date.today().isoformat(), 'cost': '0',
        'description': 'Capstone QA visual inspection',
    })
    assert maintenance.status_code == 302
    maintenance_page = encoder.get('/asset-operations?view=maintenance')
    assert maintenance_page.status_code == 200
    assert b'Recorded By' in maintenance_page.data and b'Inventory Encoder' in maintenance_page.data


def test_draft_controls_are_loaded_and_workflow_forms_are_annotated(app_module):
    base = (app_module.BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
    assert 'js/drafts-ui.js' in base
    for template, marker in [
        ('inventory.html', 'inventory-item'), ('requests.html', 'stock-request'), ('requisitions.html', 'purchase-requisition'),
        ('procurement.html', 'purchase-order'), ('asset_operations.html', 'asset-transfer'),
        ('asset_controls.html', 'stock-adjustment'),
    ]:
        source = (app_module.BASE_DIR / 'templates' / template).read_text(encoding='utf-8')
        assert f'data-draft-form="{marker}"' in source


def test_phase2_6_ui_accessibility_and_placeholders_are_present(app_module):
    base = (app_module.BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
    app_js = (app_module.BASE_DIR / 'static/js/app.js').read_text(encoding='utf-8')
    css = (app_module.BASE_DIR / 'static/css/app.css').read_text(encoding='utf-8')
    assert 'profileMenuToggle' in base and 'Settings' in base and 'Log Out' in base
    assert 'data-open-notification' in app_js and "markNotificationsRead" in app_js
    assert '.field-invalid' in css and '.flash.success' in css
    for template in ('inventory.html', 'requests.html', 'assignments.html', 'users.html', 'asset_operations.html'):
        source = (app_module.BASE_DIR / 'templates' / template).read_text(encoding='utf-8')
        assert 'Choose ' in source or 'choose ' in source


def test_legacy_shared_notification_reads_are_backfilled_per_current_account(app_module):
    # Older releases stored read state on the shared notification row. On migration,
    # every current eligible recipient inherits the prior state independently.
    first = _new_user(app_module, 'Encoder')
    second = _new_user(app_module, 'Encoder')
    conn = app_module.db()
    conn.execute(
        "INSERT INTO notifications(recipient_role,recipient_user,title,message,kind,read_flag,created_at) VALUES(?,NULL,?,?,?,?,?)",
        ('Encoder', 'Legacy shared read', 'Created before per-account read tracking.', 'info', 1, app_module.now()),
    )
    notification_id = conn.execute('SELECT MAX(id) id FROM notifications').fetchone()['id']
    conn.commit()
    conn.close()

    app_module.init_db()

    conn = app_module.db()
    legacy = conn.execute('SELECT read_flag FROM notifications WHERE id=?', (notification_id,)).fetchone()
    eligible = conn.execute("SELECT id FROM users WHERE role='Encoder' AND active=1").fetchall()
    markers = conn.execute('SELECT user_id FROM notification_reads WHERE notification_id=?', (notification_id,)).fetchall()
    conn.close()
    assert legacy['read_flag'] == 0
    assert {row['user_id'] for row in markers} == {row['id'] for row in eligible}

    # An account created after migration must not inherit the old shared read flag.
    late_email, late_password = _new_user(app_module, 'Encoder')
    late = app_module.app.test_client()
    assert late.post('/login', data={'email': late_email, 'password': late_password}).status_code == 302
    payload = late.get('/api/notifications').json
    late_notification = next(row for row in payload['items'] if row['id'] == notification_id)
    assert late_notification['read_flag'] == 0


def test_assignment_crossing_low_stock_threshold_generates_alert(app, app_module, hr_client, monkeypatch):
    monkeypatch.setattr(app_module, 'send_email', lambda *args, **kwargs: None)
    item_id = create_item(hr_client, qty=2, min_qty=1, max_qty=10)
    conn = app_module.db()
    employee_id = conn.execute("SELECT id FROM users WHERE role='Employee' AND active=1 LIMIT 1").fetchone()['id']
    before = conn.execute('SELECT qty,item_no FROM inventory WHERE id=?', (item_id,)).fetchone()
    conn.close()

    response = hr_client.post('/assignments/create', data={
        '_csrf': get_csrf_token(hr_client), 'inventory_id': str(item_id),
        'employee_id': str(employee_id), 'quantity': '1', 'notes': 'Threshold alert demonstration',
    })
    assert response.status_code == 302
    assert app_module.get_item(item_id)['qty'] == 1
    conn = app_module.db()
    alerts = conn.execute(
        "SELECT COUNT(*) n FROM notifications WHERE kind='low_stock' AND message LIKE ?",
        (f'%{before["item_no"]}%',),
    ).fetchone()['n']
    movement = conn.execute(
        "SELECT COUNT(*) n FROM movements WHERE inventory_id=? AND movement_type='out' AND note LIKE 'Assigned to %'",
        (item_id,),
    ).fetchone()['n']
    conn.close()
    assert alerts == 3 and movement == 1


def test_xlsx_bulk_import_accepts_excel_dates_and_records_opening_stock(app, app_module):
    from openpyxl import Workbook

    encoder = role_client(app, 'Encoder')
    name = 'Excel Bulk QA ' + secrets.token_hex(4)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['item_no', 'code', 'name', 'category', 'unit', 'qty', 'max_qty', 'min_qty', 'cost', 'received_date'])
    sheet.append([None, None, name, 'Office Supplies', 'box', 4, 12, 2, 18.75, date.today()])
    data = io.BytesIO()
    workbook.save(data)
    data.seek(0)

    preview = encoder.post('/inventory/import/preview', data={
        '_csrf': get_csrf_token(encoder), 'upload': (data, 'capstone-stock.xlsx'),
    }, content_type='multipart/form-data')
    assert preview.status_code == 200
    assert b'All 1 rows passed validation' in preview.data
    batch = re.search(rb'name="batch_id" value="([^"]+)"', preview.data)
    assert batch
    response = encoder.post('/inventory/import/confirm', data={
        '_csrf': get_csrf_token(encoder), 'batch_id': batch.group(1).decode(),
    })
    assert response.status_code == 302

    conn = app_module.db()
    item = conn.execute('SELECT * FROM inventory WHERE name=?', (name,)).fetchone()
    movement = conn.execute(
        "SELECT * FROM movements WHERE inventory_id=? AND note='Bulk import opening stock'",
        (item['id'],),
    ).fetchone()
    conn.close()
    assert item['qty'] == 4 and item['received_date'] == date.today().isoformat()
    assert movement and movement['quantity'] == 4


def test_bulk_import_confirmation_is_bound_to_creator_and_single_use(app, app_module):
    encoder = role_client(app, 'Encoder')
    name = 'Private Preview QA ' + secrets.token_hex(4)
    csv_data = (
        'name,category,unit,qty,max_qty,min_qty,cost,received_date\n'
        f'{name},Office Supplies,piece,1,5,0,2,{date.today().isoformat()}\n'
    ).encode('utf-8')
    preview = encoder.post('/inventory/import/preview', data={
        '_csrf': get_csrf_token(encoder), 'upload': (io.BytesIO(csv_data), 'private.csv'),
    }, content_type='multipart/form-data')
    batch = re.search(rb'name="batch_id" value="([^"]+)"', preview.data)
    assert batch
    batch_id = batch.group(1).decode()

    other_email, other_password = _new_user(app_module, 'Encoder')
    other = app.test_client()
    assert other.post('/login', data={'email': other_email, 'password': other_password}).status_code == 302
    denied = other.post('/inventory/import/confirm', data={
        '_csrf': get_csrf_token(other), 'batch_id': batch_id,
    })
    assert denied.status_code == 404

    accepted = encoder.post('/inventory/import/confirm', data={
        '_csrf': get_csrf_token(encoder), 'batch_id': batch_id,
    })
    assert accepted.status_code == 302
    replay = encoder.post('/inventory/import/confirm', data={
        '_csrf': get_csrf_token(encoder), 'batch_id': batch_id,
    })
    assert replay.status_code == 409
    conn = app_module.db()
    count = conn.execute('SELECT COUNT(*) n FROM inventory WHERE name=?', (name,)).fetchone()['n']
    conn.close()
    assert count == 1


def test_procurement_requisition_order_and_partial_receiving_regression(app, app_module, hr_client, monkeypatch):
    monkeypatch.setattr(app_module, 'send_email', lambda *args, **kwargs: None)
    item_id = create_item(hr_client, qty=5, min_qty=1, max_qty=30)
    original_qty = app_module.get_item(item_id)['qty']
    officer_email, officer_password = _new_user(app_module, 'Requisition Officer')
    officer = app.test_client()
    assert officer.post('/login', data={'email': officer_email, 'password': officer_password}).status_code == 302

    prepared = officer.post('/requisitions/create', data={
        '_csrf': get_csrf_token(officer), 'inventory_id': str(item_id), 'description': 'Capstone procurement replenishment',
        'quantity': '6', 'justification': 'Demonstrate requisition-to-receipt workflow',
        'needed_by': date.today().isoformat(),
    })
    assert prepared.status_code == 302
    conn = app_module.db()
    requisition = conn.execute(
        "SELECT * FROM purchase_requisitions WHERE description='Capstone procurement replenishment' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    vendor = conn.execute("SELECT id FROM vendors WHERE status='Active' ORDER BY id LIMIT 1").fetchone()
    conn.close()
    assert requisition and requisition['status'] == 'Pending Approval' and vendor

    approval = hr_client.post(f"/procurement/requisition/{requisition['id']}/decision", data={
        '_csrf': get_csrf_token(hr_client), 'decision': 'approve', 'note': 'Approved for capstone demo',
    })
    assert approval.status_code == 302
    po = officer.post('/procurement/purchase-order', data={
        '_csrf': get_csrf_token(officer), 'requisition_id': str(requisition['id']),
        'vendor_id': str(vendor['id']), 'unit_cost': '25.50', 'notes': 'Capstone demonstration purchase order',
    })
    assert po.status_code == 302
    conn = app_module.db()
    order = conn.execute('SELECT * FROM purchase_orders WHERE requisition_id=?', (requisition['id'],)).fetchone()
    conn.close()
    assert order and order['status'] == 'Ordered'
    item = app_module.get_item(item_id)
    orders_page = officer.get('/procurement?stage=orders')
    assert orders_page.status_code == 200
    assert requisition['pr_no'].encode() in orders_page.data
    assert order['po_no'].encode() in orders_page.data
    assert item['name'].encode() in orders_page.data
    assert b'Ordered' in orders_page.data

    encoder = role_client(app, 'Encoder')
    receipt = encoder.post(f"/procurement/purchase-order/{order['id']}/receive", data={
        '_csrf': get_csrf_token(encoder), 'delivered_qty': '6', 'accepted_qty': '4',
        'condition_notes': 'Two units arrived damaged and were rejected.',
    })
    assert receipt.status_code == 302
    conn = app_module.db()
    updated_order = conn.execute('SELECT * FROM purchase_orders WHERE id=?', (order['id'],)).fetchone()
    saved_receipt = conn.execute('SELECT * FROM purchase_receipts WHERE purchase_order_id=?', (order['id'],)).fetchone()
    movement = conn.execute(
        "SELECT * FROM movements WHERE inventory_id=? AND note LIKE 'Purchase receiving %' ORDER BY id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    updated_requisition = conn.execute('SELECT status FROM purchase_requisitions WHERE id=?', (requisition['id'],)).fetchone()
    conn.close()
    assert app_module.get_item(item_id)['qty'] == original_qty + 4
    assert updated_order['received_qty'] == 6 and updated_order['status'] == 'Received'
    assert saved_receipt['accepted_qty'] == 4 and saved_receipt['rejected_qty'] == 2
    assert movement and movement['quantity'] == 4
    assert updated_requisition['status'] == 'Received'


def test_role_navigation_hides_modules_outside_role_policy(app, app_module):
    expected = {
        'Super User': {'/inventory', '/users', '/procurement', '/reports-v4', '/assignments', '/requests'},
        'Admin': {'/inventory', '/users', '/procurement', '/reports-v4', '/assignments', '/requests'},
        'Inventory Manager': {'/inventory', '/procurement', '/reports-v4', '/assignments', '/requests'},
        'Encoder': {'/inventory', '/procurement', '/assignments', '/requests'},
        'Requisition Officer': {'/procurement'},
        'Finance': {'/procurement', '/reports-v4'},
        'Report Generator': {'/reports-v4'},
        'Employee': {'/assignments', '/requests'},
    }
    seeded = {
        'Super User': ('admin@ecmci.com', 'admin123'),
        'Encoder': ('encoder@ecmci.com', 'encoder123'),
        'Report Generator': ('reports@ecmci.com', 'report123'),
        'Employee': ('employee@ecmci.com', 'employee123'),
    }
    for role, allowed_links in expected.items():
        if role in seeded:
            email, password = seeded[role]
        else:
            email, password = _new_user(app_module, role)
        client = app.test_client()
        assert client.post('/login', data={'email': email, 'password': password}).status_code == 302
        page = client.get('/').data.decode('utf-8')
        nav_match = re.search(r'<nav class="workspace-nav"[^>]*>(.*?)</nav>', page, re.S)
        assert nav_match, 'role-based navigation must be rendered'
        nav = nav_match.group(1)
        for path in expected:
            assert (f'href="{path}"' in nav) == (path in allowed_links), (role, path)
        assert 'href="/settings"' in page and 'href="/logout"' in page
        client.get('/logout')



def test_low_stock_transition_uses_smtp_when_configured(app_module, hr_client, it_client, monkeypatch):
    import smtplib

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=10):
            assert host == 'smtp.capstone.test' and int(port) == 587
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def starttls(self):
            return None
        def login(self, username, password):
            assert username == 'capstone@example.test' and password == 'demo-app-password'
        def send_message(self, message):
            sent.append(message)

    monkeypatch.setenv('SMTP_HOST', 'smtp.capstone.test')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_STARTTLS', '1')
    monkeypatch.setenv('SMTP_USER', 'capstone@example.test')
    monkeypatch.setenv('SMTP_PASSWORD', 'demo-app-password')
    monkeypatch.setenv('SMTP_FROM', 'capstone@example.test')
    monkeypatch.setattr(smtplib, 'SMTP', FakeSMTP)

    item_id = create_item(hr_client, qty=3, min_qty=2, max_qty=10)
    result = it_client.post('/api/movement', json={
        'inventory_id': item_id, 'movement_type': 'out', 'quantity': 2,
        'note': 'Email notification acceptance test',
    }, headers=_csrf(it_client))
    assert result.status_code == 200
    # The bundled capstone data has one active Super User mailbox. Other role
    # recipients may be added through Users and will receive their own messages.
    assert len(sent) == 1
    assert 'Low stock alert' in sent[0]['Subject']
    assert sent[0]['To'] == 'admin@ecmci.com'
    assert 'remaining' in sent[0].get_content()
