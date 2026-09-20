from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import editor, get_current_user
from app.video_creator import jobs, routes


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    app = FastAPI()
    app.include_router(routes.router, prefix='/video-creator')
    app.dependency_overrides[editor] = lambda: SimpleNamespace(id='owner')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='owner')
    with TestClient(app) as client:
        yield client


def seed(tmp_path, owner='owner', status='complete'):
    job = dict(id=str(uuid4()), owner=owner, status=status, kind='indian-law')
    jobs.save(job)
    folder = tmp_path / job['id']
    folder.mkdir()
    (folder / 'history.mp4').write_bytes(b'test video')
    (folder / 'voice-1.mp3').write_bytes(b'test audio')
    return job, folder


def test_delete_removes_record_and_all_artifacts(client, tmp_path):
    job, folder = seed(tmp_path)
    other, other_folder = seed(tmp_path)
    response = client.post(f"/video-creator/jobs/{job['id']}/delete")
    assert response.status_code == 200
    assert response.json()['data']['deleted'] is True
    assert jobs.get(job['id'], 'owner') is None
    assert not folder.exists()
    assert other_folder.exists()
    assert jobs.get(other['id'], 'owner')
    assert client.get(f"/video-creator/jobs/{job['id']}/download").status_code == 404
    assert client.post(f"/video-creator/jobs/{job['id']}/delete").status_code == 404
    assert not jobs.gate.locked()


def test_cannot_delete_another_owners_video(client, tmp_path):
    job, folder = seed(tmp_path, owner='someone-else')
    assert client.post(f"/video-creator/jobs/{job['id']}/delete").status_code == 404
    assert folder.exists()
    assert jobs.get(job['id'], 'someone-else')


@pytest.mark.parametrize('status', ['writing', 'rendering'])
def test_active_video_cannot_be_deleted(client, tmp_path, status):
    job, folder = seed(tmp_path, status=status)
    assert client.post(f"/video-creator/jobs/{job['id']}/delete").status_code == 409
    assert folder.exists()
    assert not jobs.gate.locked()


def test_file_error_keeps_record_for_retry(client, tmp_path, monkeypatch):
    job, folder = seed(tmp_path)

    def fail(path):
        raise PermissionError('video open')

    monkeypatch.setattr(jobs.shutil, 'rmtree', fail)
    assert client.post(f"/video-creator/jobs/{job['id']}/delete").status_code == 409
    assert jobs.get(job['id'], 'owner')
    assert folder.exists()
    assert not jobs.gate.locked()


def test_stale_render_request_cannot_resurrect_deleted_job(client, tmp_path):
    job, _ = seed(tmp_path, status='review')
    assert jobs.delete(job['id'], 'owner')
    with pytest.raises(ValueError, match='deleted'):
        jobs.launch(job, 'render')
    assert jobs.get(job['id'], 'owner') is None
    assert not jobs.gate.locked()
