"""Signed download links: the mobile-safe path that streams an MP4 without the
Authorization header (so iOS/Android can hand it to their native download manager)."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.video_creator import jobs, routes

DAY = '2026-10-27'
JOB_ID = '0f2f9a16-5a4e-4f58-9f9a-9f0f6a5b7c11'
OWNER = '6bd4c2f0-2a1e-4b3c-8d5f-0a1b2c3d4e5f'
INTRUDER = '9c8b7a60-1f2e-4d3c-8b5a-6f7e8d9c0b1a'


def _app(monkeypatch, tmp_path, owner=OWNER, create_job=True):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    app = FastAPI()
    app.include_router(routes.router, prefix='/video-creator')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=owner)
    if create_job:
        jobs.save(dict(id=JOB_ID, owner=owner, status='complete', kind='news', date=DAY))
        (tmp_path / JOB_ID).mkdir()
        (tmp_path / JOB_ID / 'history.mp4').write_bytes(b'video-bytes')
    return app


def test_signed_link_downloads_without_an_auth_header(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        link = client.post(f'/video-creator/jobs/{JOB_ID}/download-link', json={'format': 'landscape'})
        assert link.status_code == 200
        token = link.json()['data']['token']
        assert link.json()['data']['expires_in'] > 0
        # A fresh client without any session cookie/token: the URL must still work.
        response = TestClient(app).get(f'/video-creator/download/{token}')
    assert response.status_code == 200
    assert response.content == b'video-bytes'
    assert 'tamil-news-2026-10-27.mp4' in response.headers['content-disposition']
    assert response.headers['content-type'] == 'video/mp4'


def test_tampered_or_missing_token_is_rejected(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        token = client.post(f'/video-creator/jobs/{JOB_ID}/download-link', json={}).json()['data']['token']
        tampered = token[:-2] + ('AA' if not token.endswith('AA') else 'BB')
        assert client.get(f'/video-creator/download/{tampered}').status_code == 401
        assert client.get('/video-creator/download/not-a-token').status_code == 401


def test_link_is_scoped_to_the_owner(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(f'/video-creator/jobs/{JOB_ID}/download-link', json={})
    assert response.status_code == 200
    # Someone else cannot mint a link for this job at all.
    other = _app(monkeypatch, tmp_path, owner=INTRUDER, create_job=False)
    with TestClient(other) as client:
        assert client.post(f'/video-creator/jobs/{JOB_ID}/download-link', json={}).status_code == 404
