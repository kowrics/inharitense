"""Shared pytest fixtures.

Critically, this points the app at an isolated temp SQLite file via
SQLITE_DB_PATH (set BEFORE app.py is imported) so tests never touch the real
inharitense.db development database. The app module is imported once per test
session using importlib so it doesn't collide with a normal `import app`
elsewhere.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='session')
def app_module():
    fd, path = tempfile.mkstemp(prefix='inharitense_test_', suffix='.db')
    os.close(fd)
    os.remove(path)  # let init_db() create it fresh
    os.environ['SQLITE_DB_PATH'] = path
    os.environ.setdefault('APP_ENV', 'development')
    os.environ.setdefault('SECRET_KEY', 'test-only-secret-not-for-production')

    spec = importlib.util.spec_from_file_location('inharitense_app_under_test', ROOT / 'app.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['inharitense_app_under_test'] = module
    spec.loader.exec_module(module)

    yield module

    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture()
def app(app_module):
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


# Demo accounts seeded by init_db() in non-production mode (see app.py DEFAULT_USERS).
CREDENTIALS = {
    'HR': ('admin@ecmci.com', 'admin123'),
    'Purchasing': ('reports@ecmci.com', 'report123'),
    'IT Custodian': ('encoder@ecmci.com', 'encoder123'),
    'Department User': ('employee@ecmci.com', 'employee123'),
}


def login_as(client, role):
    email, password = CREDENTIALS[role]
    resp = client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)
    assert resp.status_code == 200
    return resp


def get_csrf_token(client):
    """Read the CSRF token the app already put in the session (base.html/login.html
    call csrf_token() on every render, which lazily creates it)."""
    with client.session_transaction() as sess:
        token = sess.get('_csrf')
    if token:
        return token
    # Not created yet in this test's session — visit a page that renders it.
    client.get('/login')
    with client.session_transaction() as sess:
        return sess.get('_csrf')



# Each role fixture gets its OWN test client (own cookiejar/session) rather than sharing
# `client` — a test that uses more than one role at once (e.g. the request/approval/
# fulfillment workflow) needs genuinely independent logins in flight simultaneously.

@pytest.fixture()
def hr_client(app):
    c = app.test_client()
    login_as(c, 'HR')
    return c


@pytest.fixture()
def purchasing_client(app):
    c = app.test_client()
    login_as(c, 'Purchasing')
    return c


@pytest.fixture()
def it_client(app):
    c = app.test_client()
    login_as(c, 'IT Custodian')
    return c


@pytest.fixture()
def employee_client(app):
    c = app.test_client()
    login_as(c, 'Department User')
    return c
