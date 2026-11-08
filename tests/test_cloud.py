"""Durable cloud behavior uses an isolated in-memory Blob transport, not real customer data."""
from datetime import datetime, timezone
import hashlib
import json
import time
from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app import cloud_database, cloud_storage, main, ml
from backend.app.cloud_session import COOKIE_NAME, signed_cookie, verify_cookie
from backend.app.config import RUNTIME
from backend.app.data import BASE


class MissingBlob(Exception):
    pass


class DuplicateBlob(Exception):
    status_code = 409


class FakeBlob:
    BlobNotFoundError = MissingBlob

    def __init__(self):
        self.objects = {}

    def put_blob(self, pathname, body, **options):
        assert options['access'] == 'private' and not options['allow_overwrite']
        if pathname in self.objects:
            raise DuplicateBlob('already exists')
        self.objects[pathname] = (bytes(body), datetime.now(timezone.utc))
        return SimpleNamespace(etag=hashlib.sha256(body).hexdigest())

    def get_blob(self, pathname, **options):
        assert options['access'] == 'private'
        if pathname not in self.objects:
            raise MissingBlob(pathname)
        body=self.objects[pathname][0]
        return SimpleNamespace(body=body,metadata=SimpleNamespace(etag=hashlib.sha256(body).hexdigest()))

    def delete_blob(self, pathname, if_match):
        body=self.objects[pathname][0]
        assert hashlib.sha256(body).hexdigest()==if_match
        del self.objects[pathname]

    def head_blob(self, pathname):
        if pathname not in self.objects:
            raise MissingBlob(pathname)
        return SimpleNamespace(pathname=pathname)

    def query_blobs(self, prefix, page_size):
        return iter([SimpleNamespace(pathname=k, uploaded_at=v[1]) for k,v in self.objects.items() if k.startswith(prefix)])


@pytest.fixture
def cloud(monkeypatch):
    transport = FakeBlob()
    monkeypatch.setenv('CLOUD_SESSION_SECRET', 'cloud-test-secret-with-at-least-32-characters')
    monkeypatch.setattr(main, 'CLOUD_DEMO', True)
    monkeypatch.setattr(ml, 'CLOUD_DEMO', True)
    monkeypatch.setattr(cloud_storage, 'sdk', lambda: transport)
    for name in ['save', 'get', 'listing']:
        monkeypatch.setattr(main.db, name, getattr(cloud_database, name))
    return transport


def test_cloud_cookie_integrity(monkeypatch):
    monkeypatch.setenv('CLOUD_SESSION_SECRET', 'cloud-test-secret-with-at-least-32-characters')
    identifier = str(uuid.uuid4())
    cookie = signed_cookie(identifier)
    assert verify_cookie(cookie) == identifier
    assert verify_cookie(cookie[:-1]+('a' if cookie[-1] != 'a' else 'b')) is None
    assert verify_cookie('not-a-cookie') is None
    assert verify_cookie(None) is None


def test_cloud_persistence_and_workspace_isolation(cloud):
    a = TestClient(main.app, base_url='https://research.example')
    b = TestClient(main.app, base_url='https://research.example')
    register(a,'a@example.test')
    register(b,'b@example.test')
    assert a.get('/api/data/datasets').json() == []
    assert a.cookies.get(COOKIE_NAME)
    response = a.post('/api/data/synthetic', json={'n': 1000})
    assert response.status_code == 200, response.text
    d = response.json()
    assert b.get('/api/data/datasets').json() == []
    assert b.get('/api/data/datasets/'+d['id']).status_code == 404
    # Simulate losing the instance-local dataset file.
    (RUNTIME / (d['file_id']+'.csv')).unlink()
    model_response = a.post('/api/prediction/train', json={'dataset_id': d['id']})
    assert model_response.status_code == 200, model_response.text
    model = model_response.json()
    (RUNTIME / (model['artifact_id']+'.joblib')).unlink()
    borrower = {k:d['preview'][0][k] for k in BASE}
    prediction = a.post('/api/prediction/predict', json={'model_id': model['id'], 'borrower': borrower})
    assert prediction.status_code == 200, prediction.text
    assert abs(prediction.json()['explanation']['additivity_residual']) < 1e-6
    assert len(a.get('/api/prediction/models').json()) == 1
    assert b.get('/api/prediction/models').json() == []
    assert any('/artifacts/' in k for k in cloud.objects)


def test_cloud_origin_bootstrap_and_private_upload_guard(cloud):
    client = TestClient(main.app, base_url='https://research.example')
    assert client.post('/api/data/synthetic', json={}).status_code == 401
    assert client.get('/api/data/datasets', headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.get('/api/health').json()['persistence'] == 'private_vercel_blob'
    register(client,'guard@example.test')
    assert client.post('/api/data/synthetic', json={'n':3001}).status_code == 422
    assert client.post('/api/data/upload', files={'file':('data.csv','x\n1')},
        data={'source':'test','license':'test','target_definition':'test'}).status_code == 403


def test_cloud_storage_requires_workspace():
    with pytest.raises(PermissionError):
        cloud_storage.prefix()


PASSWORD='Synthetic research passphrase 2026'


def register(client,email='researcher@example.test'):
    response=client.post('/api/auth/register',json={'email':email,'password':PASSWORD})
    assert response.status_code==200,response.text
    return response.json()['user']


def test_real_login_password_hashes_and_duplicate_accounts(cloud):
    client=TestClient(main.app,base_url='https://research.example')
    assert client.get('/api/auth/session').json()['authenticated'] is False
    assert client.get('/api/data/datasets').status_code==401
    account=register(client)
    assert 'password' not in client.get('/api/auth/session').text
    records=[json.loads(v[0]) for k,v in cloud.objects.items() if 'auth/accounts/' in k]
    assert records[0]['password']['algorithm']=='scrypt'
    assert PASSWORD not in str(records)
    assert client.post('/api/auth/register',json={'email':' RESEARCHER@example.test ','password':PASSWORD}).status_code==409
    other=TestClient(main.app,base_url='https://research.example')
    bad=other.post('/api/auth/login',json={'email':account['email'],'password':'incorrect password'})
    assert bad.status_code==401 and 'incorrect password' not in bad.text
    result=other.post('/api/auth/login',json={'email':account['email'],'password':PASSWORD})
    assert result.status_code==200 and result.json()['user']['id']==account['id']


def test_account_auto_setup_is_reused_across_browsers(cloud):
    first=TestClient(main.app,base_url='https://research.example')
    register(first)
    prepared=first.post('/api/workspace/initialize',json={})
    assert prepared.status_code==200,prepared.text
    assert prepared.json()['created'] is True
    assert len(first.get('/api/data/datasets').json())==1
    assert len(first.get('/api/prediction/models').json())==1
    other=TestClient(main.app,base_url='https://research.example')
    assert other.post('/api/auth/login',json={'email':'researcher@example.test','password':PASSWORD}).status_code==200
    restored=other.post('/api/workspace/initialize',json={})
    assert restored.status_code==200,restored.text
    assert restored.json()['created'] is False
    assert restored.json()['dataset_id']==prepared.json()['dataset_id']
    assert restored.json()['model_id']==prepared.json()['model_id']
    assert len(other.get('/api/prediction/models').json())==1


def test_logout_revokes_replayed_session(cloud):
    client=TestClient(main.app,base_url='https://research.example')
    register(client)
    cookie=client.cookies.get(COOKIE_NAME)
    assert client.post('/api/auth/logout',json={}).status_code==200
    assert client.get('/api/data/datasets').status_code==401
    replay=TestClient(main.app,base_url='https://research.example')
    replay.cookies.set(COOKIE_NAME,cookie)
    assert replay.get('/api/auth/session').json()['authenticated'] is False
    assert replay.get('/api/data/datasets').status_code==401


def test_revocation_uses_metadata_even_if_delivery_caches_missing(cloud,monkeypatch):
    client=TestClient(main.app,base_url='https://research.example')
    register(client)
    cookie=client.cookies.get(COOKIE_NAME)
    actual_get=cloud.get_blob
    def stale_delivery(pathname,**options):
        if '/revoked/' in pathname:
            raise MissingBlob(pathname)
        return actual_get(pathname,**options)
    monkeypatch.setattr(cloud,'get_blob',stale_delivery)
    assert client.post('/api/auth/logout',json={}).status_code==200
    replay=TestClient(main.app,base_url='https://research.example')
    replay.cookies.set(COOKIE_NAME,cookie)
    assert replay.get('/api/data/datasets').status_code==401


def test_sessions_expire_and_validation_never_echoes_password(cloud,monkeypatch):
    from backend.app import cloud_session
    monkeypatch.setattr(cloud_session.time,'time',lambda:100000)
    cookie=signed_cookie(str(uuid.uuid4()))
    monkeypatch.setattr(cloud_session.time,'time',lambda:100000+cloud_session.SESSION_TTL+1)
    assert verify_cookie(cookie) is None
    client=TestClient(main.app,base_url='https://research.example')
    secret='p'*129
    result=client.post('/api/auth/register',json={'email':'user@example.test','password':secret})
    assert result.status_code==422 and secret not in result.text


def test_auth_attempts_are_bounded_across_requests(cloud):
    client=TestClient(main.app,base_url='https://research.example')
    for _ in range(10):
        assert client.post('/api/auth/login',json={'email':'nobody@example.test','password':PASSWORD}).status_code==401
    assert client.post('/api/auth/login',json={'email':'nobody@example.test','password':PASSWORD}).status_code==429
