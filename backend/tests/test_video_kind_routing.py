from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import editor
from app.video_creator import jobs, routes


@pytest.mark.parametrize('kind,count,lines', [('history', 10, 2), ('indian-law', 5, 4), ('make-money', 5, 4)])
def test_http_request_selects_and_persists_correct_script(monkeypatch, tmp_path, kind, count, lines):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    history_calls = []

    def video_script(kind, day, progress):
        if kind == 'history':
            history_calls.append(day)
            return [dict(source_id=i, year='1900', lines=['வரலாற்று நிகழ்வு.'] * 2) for i in range(10)]
        if kind == 'indian-law':
            return [dict(title=f'Act {i}', sections=[str(i)], lines=['சட்டம்.'] * 4) for i in range(5)]
        return [dict(title=f'Idea {i}', title_en=f'Idea {i}', topic='money', photo_query='money',
                     lines=['பணம்.'] * 4) for i in range(5)]

    monkeypatch.setattr(jobs, 'create_video_script', video_script)

    def immediate_launch(job, action):
        assert jobs.gate.acquire(blocking=False)
        jobs.run(job, action)
        return job

    monkeypatch.setattr(jobs, 'launch', immediate_launch)
    app = FastAPI()
    app.include_router(routes.router, prefix='/video-creator')
    app.dependency_overrides[editor] = lambda: SimpleNamespace(id='kind-test-owner')
    with TestClient(app) as client:
        response = client.post('/video-creator/jobs', json={'kind': kind, 'day': '2026-09-17'})
    assert response.status_code == 202
    job = response.json()['data']
    saved = jobs.get(job['id'], 'kind-test-owner')
    assert saved['kind'] == kind
    assert saved['status'] == 'review'
    assert len(saved['points']) == count
    assert all(len(p['lines']) == lines for p in saved['points'])
    assert bool(history_calls) == (kind == 'history')
    if kind == 'indian-law':
        assert all('Act' in p['title'] and p['sections'] for p in saved['points'])
    if kind == 'make-money':
        assert saved['model'] == 'curated-tamil-v1'
        assert all(p['title'] and p['title_en'] and p['topic'] and p['photo_query'] for p in saved['points'])
    assert not jobs.gate.locked()
