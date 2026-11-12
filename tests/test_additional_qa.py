"""Regression coverage for the additional November 2026 client QA findings."""
import secrets
from pathlib import Path


from tests.conftest import get_csrf_token
from tests.test_refinements import create_item


def _csrf(client):
    return {'X-CSRFToken': get_csrf_token(client)}


def test_audit_trail_template_compiles_without_duplicate_script_blocks(app_module):
    # Compiling the template (not only parsing it) catches duplicate Jinja blocks.
    template = app_module.app.jinja_env.get_template('audit_trail.html')
    assert template is not None


def test_physical_inventory_requires_every_count_and_variance_explanation(app_module, hr_client):
    item_id = create_item(hr_client, qty=7, min_qty=1, max_qty=20)
    item = app_module.get_item(item_id)
    created = hr_client.post('/inventory-audit/create', data={
        '_csrf': get_csrf_token(hr_client), 'title': 'Required Fields QA',
        'category': item['category'],
    })
    assert created.status_code == 302
    audit_url = created.headers['Location']
    audit_id = int(audit_url.rstrip('/').split('/')[-1])

    conn = app_module.db()
    rows = conn.execute('SELECT * FROM inventory_audit_items WHERE audit_id=? ORDER BY id', (audit_id,)).fetchall()
    audit = conn.execute('SELECT draft_revision FROM inventory_audits WHERE id=?', (audit_id,)).fetchone()
    conn.close()
    assert rows

    missing = hr_client.post(audit_url, headers={**_csrf(hr_client), 'Accept': 'application/json'}, data={
        'audit_action': 'finalize', 'draft_revision': str(audit['draft_revision']),
    })
    assert missing.status_code == 422
    assert missing.json['field_errors']
    assert any(key.startswith('actual_') for key in missing.json['field_errors'])

    payload = {'audit_action': 'finalize', 'draft_revision': str(audit['draft_revision'])}
    for row in rows:
        payload[f'actual_{row["id"]}'] = str(row['expected_qty'])
    first = rows[0]
    payload[f'actual_{first["id"]}'] = str(first['expected_qty'] + 1)
    missing_note = hr_client.post(audit_url, headers={**_csrf(hr_client), 'Accept': 'application/json'}, data=payload)
    assert missing_note.status_code == 422
    assert f'notes_{first["id"]}' in missing_note.json['field_errors']

    payload[f'notes_{first["id"]}'] = 'QA discrepancy explanation.'
    finalized = hr_client.post(audit_url, headers={**_csrf(hr_client), 'Accept': 'application/json'}, data=payload)
    assert finalized.status_code == 200 and finalized.json['finalized'] is True


def test_empty_physical_inventory_audit_cannot_be_finalized(app_module, hr_client):
    created = hr_client.post('/inventory-audit/create', data={
        '_csrf': get_csrf_token(hr_client), 'title': 'Empty Audit QA',
        'category': 'Staff House Equipment',
    })
    assert created.status_code == 302
    audit_url = created.headers['Location']
    audit_id = int(audit_url.rstrip('/').split('/')[-1])
    conn = app_module.db()
    record = conn.execute('SELECT draft_revision FROM inventory_audits WHERE id=?', (audit_id,)).fetchone()
    count = conn.execute('SELECT COUNT(*) n FROM inventory_audit_items WHERE audit_id=?', (audit_id,)).fetchone()['n']
    conn.close()
    assert count == 0

    response = hr_client.post(audit_url, headers={**_csrf(hr_client), 'Accept': 'application/json'}, data={
        'audit_action': 'finalize', 'draft_revision': str(record['draft_revision']),
    })
    assert response.status_code == 422
    assert '_form' in response.json['field_errors']


def test_maintenance_draft_is_persistent_and_account_scoped(app, app_module, hr_client):
    item_id = create_item(hr_client)
    payload = {
        'inventory_id': str(item_id), 'kind': 'Repair', 'condition_after': 'Good',
        'performed_on': '2026-11-12', 'cost': '125.00',
        'description': 'Replace damaged power cable for QA.',
    }
    saved = hr_client.post('/asset-operations/maintenance/draft', json=payload, headers=_csrf(hr_client))
    assert saved.status_code == 200
    draft_id = saved.json['draft_id']

    page = hr_client.get(f'/asset-operations?view=maintenance&draft={draft_id}')
    assert page.status_code == 200
    assert b'Maintenance Drafts' in page.data
    assert b'Replace damaged power cable for QA.' in page.data

    other_email = f"maintenance-owner-{secrets.token_hex(4)}@example.com"
    conn = app_module.db()
    conn.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
                 ('Other Admin', other_email, app_module.generate_password_hash('MaintenanceQA123'), 'Admin', 'QA', app_module.now()))
    conn.commit(); conn.close()
    other = app.test_client()
    assert other.post('/login', data={'email': other_email, 'password': 'MaintenanceQA123'}).status_code == 302
    assert other.post(f'/asset-operations/maintenance/draft/{draft_id}/delete', headers=_csrf(other)).status_code == 404

    deleted = hr_client.post(f'/asset-operations/maintenance/draft/{draft_id}/delete', headers=_csrf(hr_client))
    assert deleted.status_code == 302
    conn = app_module.db()
    exists = conn.execute('SELECT 1 FROM maintenance_drafts WHERE id=?', (draft_id,)).fetchone()
    conn.close()
    assert exists is None


def test_maintenance_record_saves_back_to_maintenance_view(app_module, hr_client):
    item_id = create_item(hr_client)
    response = hr_client.post('/asset-operations/maintenance', data={
        '_csrf': get_csrf_token(hr_client), 'inventory_id': str(item_id),
        'kind': 'Inspection', 'condition_after': 'Good', 'performed_on': '2026-11-12',
        'cost': '0', 'description': 'Routine equipment inspection for QA.',
    })
    assert response.status_code == 302
    assert 'view=maintenance' in response.headers['Location']
    assert 'circulation' not in response.headers['Location']


def test_purchase_requisition_and_client_overview_generate_pdf_attachments(app_module, hr_client):
    item_id = create_item(hr_client)
    created = hr_client.post('/requisitions/create', data={
        '_csrf': get_csrf_token(hr_client), 'inventory_id': str(item_id),
        'description': 'PDF attachment QA requisition', 'quantity': '3',
        'justification': 'Verify generated PDF attachment.',
    })
    assert created.status_code == 302
    conn = app_module.db()
    record = conn.execute("SELECT id FROM purchase_requisitions WHERE description='PDF attachment QA requisition' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert record

    for path in (f'/requisitions/{record["id"]}/pdf', '/client-reports/overview.pdf', '/reports/pdf/movements'):
        response = hr_client.get(path)
        assert response.status_code == 200
        assert response.mimetype == 'application/pdf'
        assert 'attachment' in response.headers.get('Content-Disposition', '').lower()
        assert response.data.startswith(b'%PDF-')


def test_forecast_demo_data_is_sufficient_and_separate_from_live_movements(app_module, hr_client):
    conn = app_module.db()
    item = conn.execute("SELECT * FROM inventory WHERE category IN ('Office Supplies','Janitorial Supplies','Pantry Supplies','Emergency Food') ORDER BY id LIMIT 1").fetchone()
    assert item
    before_live = conn.execute('SELECT COUNT(*) n FROM movements WHERE inventory_id=?', (item['id'],)).fetchone()['n']
    demo_rows = conn.execute('SELECT COUNT(*) n FROM forecast_demo_movements WHERE inventory_id=?', (item['id'],)).fetchone()['n']
    conn.close()
    assert demo_rows >= 40

    response = hr_client.get(f'/api/forecast-demo/{item["id"]}')
    assert response.status_code == 200
    assert response.json['is_demo'] is True
    assert response.json['forecast']['data_status'] == 'Sufficient data'
    assert len(response.json['forecast']['history_weeks']) == 26
    assert any(day['outs'] > 0 for day in response.json['history'])

    conn = app_module.db()
    after_live = conn.execute('SELECT COUNT(*) n FROM movements WHERE inventory_id=?', (item['id'],)).fetchone()['n']
    conn.close()
    assert after_live == before_live


def test_notification_payload_has_workflow_target_and_only_recipient_can_read(app, app_module, hr_client, monkeypatch):
    monkeypatch.setattr(app_module, 'send_email', lambda *args, **kwargs: None)
    conn = app_module.db()
    app_module.notify('Super User', 'QA targeted notification', 'Open this record.', 'maintenance',
                      conn=conn, target_url='/asset-operations?view=maintenance#maintenance-123')
    conn.commit()
    notification_id = conn.execute("SELECT id FROM notifications WHERE title='QA targeted notification' ORDER BY id DESC LIMIT 1").fetchone()['id']
    conn.close()

    payload = hr_client.get('/api/notifications').json
    row = next(item for item in payload['items'] if item['id'] == notification_id)
    assert row['target_url'] == '/asset-operations?view=maintenance#maintenance-123'

    other_email = f"not-recipient-{secrets.token_hex(4)}@example.com"
    conn = app_module.db()
    conn.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
                 ('Encoder Not Recipient', other_email, app_module.generate_password_hash('NotificationQA123'), 'Encoder', 'QA', app_module.now()))
    conn.commit(); conn.close()
    other = app.test_client()
    assert other.post('/login', data={'email': other_email, 'password': 'NotificationQA123'}).status_code == 302
    denied = other.post(f'/api/notifications/{notification_id}/read', headers=_csrf(other))
    assert denied.status_code == 404


def test_unsaved_change_guard_covers_dynamic_forms_and_reset_confirmation():
    source = (Path(__file__).resolve().parents[1] / 'static/js/unsaved-changes.js').read_text(encoding='utf-8')
    assert 'new MutationObserver' in source
    assert "form.method.toLowerCase() === 'get'" in source
    assert "form.addEventListener('reset'" in source
    assert "form.addEventListener('ecmci:draft-submitted', markClean)" in source
    assert "modal.querySelectorAll('form')" in source
    assert "const managedClose = closeControl?.hasAttribute('data-ui-modal-close')" in source
    assert 'if (!dirty) { closeModal(modal); return; }' in source
    base = (Path(__file__).resolve().parents[1] / 'templates/base.html').read_text(encoding='utf-8')
    assert 'Continue Editing' in base and 'Discard Changes' in base


def test_global_back_navigation_and_left_drawer_controls_are_present():
    root = Path(__file__).resolve().parents[1]
    base = (root / 'templates/base.html').read_text(encoding='utf-8')
    script = (root / 'static/js/figma-ui.js').read_text(encoding='utf-8')
    styles = (root / 'static/css/figma-ui.css').read_text(encoding='utf-8')

    assert 'id="backButton"' in base
    assert "data-fallback-url=\"{{ url_for('dashboard') }}\"" in base
    assert base.index('id="backButton"') < base.index('class="page-heading"')
    assert base.index('id="navToggle"') < base.index('class="page-heading"')
    assert 'sessionStorage' in script and 'ecmci-page-history:' in script
    assert 'window.location.assign(target)' in script
    assert 'pages.splice(0, pages.length, target)' in script
    assert 'id="navToggle"' in base and 'aria-controls="appNav"' in base
    assert '.header-start' in styles and '.header-nav-controls' in styles
    assert 'var(--surface)' in styles and 'var(--line)' in styles
