from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, update
from app.database.engine import sync_engine
from app.models.user import User, UserRole

def test_health_docs_and_readiness(client):
    assert client.get('/health').json()['server'] == 'hypercorn'
    assert client.get('/ready').status_code == 200
    assert client.get('/api/docs').status_code == 200
    schema = client.get('/api/openapi.json').json()
    assert '/api/v1/auth/login' in schema['paths']
    assert not any('/api/api/' in path for path in schema['paths'])
    assert client.get('/api/does-not-exist').status_code == 404

def test_register_persists_and_login_checks_password(client, account):
    with sync_engine.connect() as db:
        row = db.execute(select(User.__table__).where(User.email == 'creator@example.com')).mappings().one()
    assert row['password_hash'].startswith('$argon2id$')
    assert account['access_token'] != 'demo'
    wrong = client.post('/api/v1/auth/login', json={'email':'creator@example.com','password':'wrong'})
    assert wrong.status_code == 401
    correct = client.post('/api/v1/auth/login', json={'email':'creator@example.com','password':'A secure password 123'})
    assert correct.status_code == 200

def test_duplicate_and_role_injection_rejected(client, account):
    payload={'email':'creator@example.com','username':'creator','password':'A secure password 123'}
    assert client.post('/api/v1/auth/register',json=payload).status_code==409
    payload.update(email='other@example.com',username='other',role='SUPER_ADMIN')
    assert client.post('/api/v1/auth/register',json=payload).status_code==422

def test_refresh_rotation_and_logout(client, account):
    old=account['refresh_token']
    response=client.post('/api/v1/auth/refresh',json={'refresh_token':old})
    assert response.status_code==200
    fresh=response.json()['data']
    assert fresh['refresh_token'] != old
    assert client.post('/api/v1/auth/refresh',json={'refresh_token':old}).status_code==401
    headers={'Authorization':f"Bearer {fresh['access_token']}"}
    assert client.post('/api/v1/auth/logout',headers=headers).status_code==200
    assert client.get('/api/v1/auth/me',headers=headers).status_code==401
    assert client.post('/api/v1/auth/refresh',json={'refresh_token':fresh['refresh_token']}).status_code==401

def test_cookie_refresh_requires_origin(client, account):
    assert client.post('/api/v1/auth/refresh').status_code==403
    assert client.post('/api/v1/auth/refresh',headers={'Origin':'https://attacker.invalid'}).status_code==403
    response=client.post('/api/v1/auth/refresh',headers={'Origin':'http://testserver'})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']

@pytest.mark.parametrize('path',['dashboard','social/accounts','settings','audit-logs','scheduler','video-creator/jobs'])
def test_auth_required(client,path):
    assert client.get('/api/v1/'+path).status_code==401

REMOVED_ENDPOINTS = ['content', 'content/000', 'ai/health', 'analytics/summary', 'affiliate/products', 'products',
                     'orders', 'revenue', 'notifications']

@pytest.mark.parametrize('path', REMOVED_ENDPOINTS)
def test_removed_modules_are_gone(client, headers, path):
    assert client.get('/api/v1/' + path, headers=headers).status_code == 404
    schema = client.get('/api/openapi.json').json()
    assert not any(p.startswith('/api/v1/' + path.split('/')[0] + '/') or p == '/api/v1/' + path.split('/')[0] for p in schema['paths'])

def test_viewer_cannot_write(client, account, headers):
    with sync_engine.begin() as db:
        db.execute(update(User).where(User.id==UUID(account['user']['id'])).values(role=UserRole.VIEWER))
    assert client.post(f'/api/v1/scheduler/{uuid4()}/pause',headers=headers).status_code==403
    assert client.post('/api/v1/video-creator/jobs',headers=headers,json={}).status_code==403
    assert client.get('/api/v1/scheduler',headers=headers).status_code==200

@pytest.mark.parametrize('method,path', [('post','social/publish'),('post','payments/checkout'),('get','videos/000/status')])
def test_incomplete_features_never_claim_success(client,headers,method,path):
    response=getattr(client,method)('/api/v1/'+path,headers=headers)
    assert response.status_code==501
    assert response.json()['success'] is False

def test_rate_limit(client):
    for _ in range(20):
        assert client.post('/api/v1/auth/login',json={'email':'nobody@example.com','password':'wrong'}).status_code==401
    response=client.post('/api/v1/auth/login',json={'email':'nobody@example.com','password':'wrong'})
    assert response.status_code==429
    assert response.headers['Retry-After']=='60'

def test_errors_hide_technical_details(client):
    @client.app.get('/test-crash')
    async def crash():
        raise RuntimeError('SECRET DATABASE CONNECTION')
    response=client.get('/test-crash')
    # Catch-all UI route precedes the test route, so insert it before the catch-all.
    client.app.router.routes.insert(0,client.app.router.routes.pop())
    response=client.get('/test-crash')
    assert response.status_code==500
    assert 'SECRET' not in response.text
    assert response.json()['error']['id']
