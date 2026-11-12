"""Phase 1 security and account-management acceptance tests."""
import re
import secrets
from datetime import timedelta

from tests.conftest import get_csrf_token, login_as


def create_user(admin_client, email, role='Encoder'):
    response = admin_client.post('/users/create', data={
        'name': 'QA Temporary User',
        'email': email,
        'role': role,
        'department': 'QA',
        '_csrf': get_csrf_token(admin_client),
    })
    return response


def read_generated_password(response):
    match = re.search(rb'<code id="generatedTemporaryPassword">([^<]+)</code>', response.data)
    assert match, 'one-time temporary password should be shown in the creation response'
    return match.group(1).decode('utf-8')


def test_new_accounts_get_unique_random_temporary_passwords_and_force_change(app, app_module):
    admin = app.test_client()
    login_as(admin, 'HR')
    first_email = f"qa-{secrets.token_hex(5)}@example.com"
    second_email = f"qa-{secrets.token_hex(5)}@example.com"

    first_response = create_user(admin, first_email)
    second_response = create_user(admin, second_email)
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert 'no-store' in first_response.headers.get('Cache-Control', '')

    first_password = read_generated_password(first_response)
    second_password = read_generated_password(second_response)
    # The generated credential must not reappear on an ordinary later GET.
    later_users_page = admin.get('/users')
    assert later_users_page.status_code == 200
    assert first_password.encode('utf-8') not in later_users_page.data
    assert second_password.encode('utf-8') not in later_users_page.data
    assert first_password != second_password
    for password in (first_password, second_password):
        assert len(password) >= 12
        assert any(ch.isalpha() for ch in password)
        assert any(ch.isdigit() for ch in password)

    c = app_module.db()
    rows = [c.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            for email in (first_email, second_email)]
    c.close()
    assert all(row['must_change_password'] == 1 for row in rows)
    assert all(row['temporary_password_fingerprint'] for row in rows)
    assert rows[0]['temporary_password_fingerprint'] != rows[1]['temporary_password_fingerprint']
    assert app_module.check_password_hash(rows[0]['password_hash'], first_password)
    assert app_module.check_password_hash(rows[1]['password_hash'], second_password)
    assert first_password not in rows[0]['password_hash']

    user_client = app.test_client()
    login_response = user_client.post('/login', data={'email': first_email, 'password': first_password})
    assert login_response.status_code == 302
    assert login_response.headers['Location'].endswith('/settings')
    restricted = user_client.get('/inventory')
    assert restricted.status_code == 302
    assert restricted.headers['Location'].endswith('/settings')

    change_response = user_client.post('/settings', data={
        'name': 'QA Temporary User',
        'email': first_email,
        'phone': '',
        'current_password': first_password,
        'new_password': 'NewSecurePassword123',
        'confirm_password': 'NewSecurePassword123',
        'save_section': 'password',
        '_csrf': get_csrf_token(user_client),
    })
    assert change_response.status_code == 302
    c = app_module.db()
    updated = c.execute('SELECT must_change_password,password_hash,auth_version FROM users WHERE email=?', (first_email,)).fetchone()
    c.close()
    assert updated['must_change_password'] == 0
    assert app_module.check_password_hash(updated['password_hash'], 'NewSecurePassword123')
    assert user_client.get('/').status_code == 200


def test_registered_email_is_read_only_and_server_rejects_changes(app, app_module):
    email = f"email-lock-{secrets.token_hex(5)}@example.com"
    c = app_module.db()
    c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
              ('Email Lock Test', email, app_module.generate_password_hash('OldSecurePass123'), 'Employee', 'QA', app_module.now()))
    c.commit()
    c.close()

    client = app.test_client()
    assert client.post('/login', data={'email': email, 'password': 'OldSecurePass123'}).status_code == 302
    page = client.get('/settings')
    assert page.status_code == 200
    assert re.search(rb'name="email"[^>]*readonly', page.data)

    changed = f"changed-{secrets.token_hex(4)}@example.com"
    response = client.post('/settings', data={
        'name': 'Email Lock Test', 'email': changed, 'phone': '',
        'save_section': 'profile', '_csrf': get_csrf_token(client),
    })
    assert response.status_code == 400
    assert b'registered email address cannot be changed' in response.data
    c = app_module.db()
    saved = c.execute('SELECT email FROM users WHERE email=?', (email,)).fetchone()
    c.close()
    assert saved and saved['email'] == email


def test_password_mismatch_does_not_change_password_and_ui_checks_before_post(app, app_module):
    email = f"password-check-{secrets.token_hex(5)}@example.com"
    c = app_module.db()
    c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
              ('Password Check', email, app_module.generate_password_hash('OldSecurePass123'), 'Employee', 'QA', app_module.now()))
    c.commit()
    c.close()

    client = app.test_client()
    assert client.post('/login', data={'email': email, 'password': 'OldSecurePass123'}).status_code == 302
    response = client.post('/settings', data={
        'name': 'Password Check', 'email': email, 'phone': '',
        'current_password': 'OldSecurePass123',
        'new_password': 'NewSecurePass123', 'confirm_password': 'DoesNotMatch123',
        'save_section': 'password', '_csrf': get_csrf_token(client),
    })
    assert response.status_code == 400
    # A correct current password is retained after only the new/confirmation fields mismatch.
    assert b'value="OldSecurePass123"' in response.data
    c = app_module.db()
    user = c.execute('SELECT password_hash FROM users WHERE email=?', (email,)).fetchone()
    c.close()
    assert app_module.check_password_hash(user['password_hash'], 'OldSecurePass123')

    security_js = (app_module.BASE_DIR / 'static/js/security-ui.js').read_text()
    assert 'setCustomValidity' in security_js
    assert 'event.preventDefault()' in security_js
    assert 'data-current-password' in (app_module.BASE_DIR / 'templates/settings.html').read_text()


def test_password_show_hide_controls_exist_on_login_and_settings(client):
    login_page = client.get('/login')
    assert login_page.status_code == 200
    assert b'data-toggle-password' in login_page.data

    login_as(client, 'HR')
    settings_page = client.get('/settings')
    assert settings_page.status_code == 200
    assert settings_page.data.count(b'data-toggle-password') == 3


def test_permanent_sessions_use_30_minute_inactivity_lifetime(app, app_module):
    assert app_module.app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(minutes=30)
    assert app_module.app.config['SESSION_REFRESH_EACH_REQUEST'] is False

    client = app.test_client()
    login_as(client, 'HR')
    with client.session_transaction() as session:
        assert session.permanent is True
        before = session['last_activity_at']
    keepalive = client.get('/session/keepalive')
    assert keepalive.status_code == 200
    assert keepalive.json == {'ok': True}
    with client.session_transaction() as session:
        assert session['last_activity_at'] >= before
    assert b'data-session-timeout-ms="1800000"' in client.get('/').data
    security_js = (app_module.BASE_DIR / 'static/js/security-ui.js').read_text()
    assert 'fetch(keepaliveUrl' in security_js


def test_background_api_polling_does_not_refresh_inactivity_marker_and_expired_session_is_rejected(app, app_module):
    import time
    client = app.test_client()
    login_as(client, 'HR')
    marker = time.time() - 60
    with client.session_transaction() as session:
        session['last_activity_at'] = marker
    # A normal notification poll is not considered user activity.
    response = client.get('/api/notifications')
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session['last_activity_at'] == marker

    # Even an API poll with the same signed cookie is rejected after 30 minutes idle.
    with client.session_transaction() as session:
        session['last_activity_at'] = time.time() - (31 * 60)
    expired = client.get('/api/notifications')
    assert expired.status_code == 302 and expired.headers['Location'].endswith('/login')
    with client.session_transaction() as session:
        assert 'user_id' not in session


def test_login_page_does_not_publish_demo_passwords(client):
    response = client.get('/login')
    assert response.status_code == 200
    for credential in (b'admin123', b'encoder123', b'report123', b'employee123', b'Demo accounts'):
        assert credential not in response.data


def test_phase1_migration_is_idempotent_and_preserves_existing_records(app_module):
    tables = ('users', 'inventory', 'movements', 'requests', 'purchase_requisitions',
              'purchase_orders', 'purchase_receipts', 'audit_logs')
    c = app_module.db()
    before = {table: c.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'] for table in tables}
    user_ids = [row['id'] for row in c.execute('SELECT id FROM users ORDER BY id').fetchall()]
    inventory_ids = [row['id'] for row in c.execute('SELECT id FROM inventory ORDER BY id').fetchall()]
    c.close()

    app_module.init_db()
    app_module.init_db()
    c = app_module.db()
    after = {table: c.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'] for table in tables}
    after_user_ids = [row['id'] for row in c.execute('SELECT id FROM users ORDER BY id').fetchall()]
    after_inventory_ids = [row['id'] for row in c.execute('SELECT id FROM inventory ORDER BY id').fetchall()]
    user_columns = {row['name'] for row in c.execute('PRAGMA table_info(users)').fetchall()}
    foreign_key_errors = c.execute('PRAGMA foreign_key_check').fetchall()
    c.close()

    assert before == after
    assert user_ids == after_user_ids
    assert inventory_ids == after_inventory_ids
    assert {'must_change_password', 'temporary_password_fingerprint'} <= user_columns
    assert foreign_key_errors == []


def test_profile_save_does_not_change_password_if_password_fields_are_filled(app, app_module):
    email = f"profile-save-{secrets.token_hex(5)}@example.com"
    original_hash = app_module.generate_password_hash('OldSecurePass123')
    c = app_module.db()
    c.execute('INSERT INTO users(name,email,password_hash,role,department,created_at) VALUES(?,?,?,?,?,?)',
              ('Profile Save Test', email, original_hash, 'Employee', 'QA', app_module.now()))
    c.commit()
    c.close()

    client = app.test_client()
    assert client.post('/login', data={'email': email, 'password': 'OldSecurePass123'}).status_code == 302
    response = client.post('/settings', data={
        'name': 'Profile Save Updated', 'email': email, 'phone': '09123456789',
        'current_password': 'OldSecurePass123',
        'new_password': 'NewSecurePass123', 'confirm_password': 'NewSecurePass123',
        'save_section': 'profile', '_csrf': get_csrf_token(client),
    })
    assert response.status_code == 302
    c = app_module.db()
    user = c.execute('SELECT name,phone,password_hash FROM users WHERE email=?', (email,)).fetchone()
    c.close()
    assert user['name'] == 'Profile Save Updated'
    assert user['phone'] == '09123456789'
    assert app_module.check_password_hash(user['password_hash'], 'OldSecurePass123')



def test_background_requests_do_not_extend_session_activity(app, app_module):
    client = app.test_client()
    login_as(client, 'HR')
    with client.session_transaction() as session:
        original_activity = session['last_activity_at']
    # Automatic notification polling must not rewrite the explicit activity marker.
    assert client.get('/api/notifications').status_code == 200
    with client.session_transaction() as session:
        assert session['last_activity_at'] == original_activity


def test_server_enforces_inactivity_timeout_even_if_cookie_is_present(app, app_module):
    client = app.test_client()
    login_as(client, 'HR')
    with client.session_transaction() as session:
        session['last_activity_at'] = app_module.time.time() - (31 * 60)
    response = client.get('/')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')
    with client.session_transaction() as session:
        assert 'user_id' not in session
