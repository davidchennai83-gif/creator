from datetime import datetime, date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.deps import editor, get_current_user
from app.api.routes.scheduler import router
from app.video_creator import schedules as s, jobs


def data(**kwargs):
    return s.ScheduleInput(**(dict(name='Morning law', project='indian-law', run_time='08:00', frequency='daily',
        start_date='2026-09-18', end_date='2026-10-31', platforms=['facebook']) | kwargs))


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    monkeypatch.setattr(s, 'now', lambda: datetime(2026, 9, 18, 7, 0, tzinfo=s.IST))
    monkeypatch.setattr(s, 'owner_allowed', lambda owner: True)
    return tmp_path


@pytest.mark.parametrize('fields,after,expected', [
    ({}, '2026-09-18T07:59:00+05:30', '2026-09-18T08:00:00+05:30'),
    ({}, '2026-09-18T08:00:00+05:30', '2026-09-19T08:00:00+05:30'),
    ({'frequency':'weekly', 'weekdays':[0, 2]}, '2026-09-18T09:00:00+05:30', '2026-09-21T08:00:00+05:30'),
    ({'frequency':'monthly', 'month_day':31, 'start_date':'2028-02-01','end_date':'2028-03-31'}, '2028-02-01T09:00:00+05:30', '2028-02-29T08:00:00+05:30'),
    ({'frequency':'custom','interval_days':3}, '2026-09-18T09:00:00+05:30', '2026-09-21T08:00:00+05:30'),
    ({'end_date':'2026-09-18'}, '2026-09-18T08:00:00+05:30', None),
])
def test_recurrence(fields, after, expected):
    assert s.next_run(data(**fields).model_dump(mode='json'), datetime.fromisoformat(after)) == expected


def test_due_task_runs_full_pipeline_once_and_busy_retries(store, monkeypatch):
    task = s.put('owner', data())
    clock = datetime(2026,9,18,8,0,tzinfo=s.IST)
    calls = []
    def generate(owner, day, voice, kind, **kwargs):
        calls.append((kind, day, kwargs))
        return {'id': kwargs['job_id']}
    monkeypatch.setattr(jobs, 'new', generate)
    jobs.gate.acquire()
    try:
        s.tick(clock)
        assert not calls
    finally:
        jobs.gate.release()
    s.tick(clock)
    s.tick(clock)
    assert len(calls) == 1
    assert calls[0][0:2] == ('indian-law', date(2026,9,18))
    assert calls[0][2]['auto_render'] is True
    saved = s.listing('owner')[0]
    assert saved['next_run'] == '2026-09-19T08:00:00+05:30'
    assert saved['publishing_status'] == 'connection_required'
    assert saved['id'] == task['id']


def test_saved_job_is_not_relaunched_after_interrupted_schedule_commit(store, monkeypatch):
    task = s.put('owner', data())
    monkeypatch.setattr(jobs, 'get', lambda *a: {'id':'already-saved', 'status':'complete'})
    def fail(*a, **kw):
        raise AssertionError('Duplicate generation')
    monkeypatch.setattr(jobs, 'new', fail)
    s.tick(datetime(2026,9,18,8,0,tzinfo=s.IST))
    assert s.listing('owner')[0]['last_job_id'] == 'already-saved'


def test_owner_isolation_pause_resume_and_delete(store):
    task = s.put('owner', data())
    assert s.listing('other') == []
    with pytest.raises(LookupError): s.change('other', task['id'], 'delete')
    assert s.change('owner', task['id'], 'pause')['enabled'] is False
    assert s.change('owner', task['id'], 'resume')['enabled'] is True
    assert s.change('owner', task['id'], 'delete')['deleted']
    assert s.listing('owner') == []


def test_api_roundtrip_and_invalid_ranges(store):
    app = FastAPI(); app.include_router(router, prefix='/scheduler')
    user = SimpleNamespace(id=str(uuid4()))
    app.dependency_overrides[editor] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        payload = data().model_dump(mode='json')
        result = client.post('/scheduler', json=payload)
        assert result.status_code == 201
        task_id = result.json()['data']['id']
        assert client.get('/scheduler').json()['data'][0]['platforms'] == ['facebook']
        projects = client.get('/scheduler/projects').json()['data']
        assert {p['id'] for p in projects if p['kind'] == 'video'} == {p['id'] for p in s.PROJECTS}
        assert all(p['kind'] in ('video', 'automation') for p in projects)
        assert client.post('/scheduler', json=payload | {'end_date':'2026-01-01'}).status_code == 422
        assert client.post('/scheduler', json=payload | {'frequency':'weekly','weekdays':[]}).status_code == 422
        assert client.put(f'/scheduler/{task_id}', json=payload | {'name':'Updated'}).status_code == 200
        assert client.delete(f'/scheduler/{task_id}').status_code == 200


def test_auto_render_reaches_mp4_in_same_job(store, monkeypatch):
    from app.video_creator import indian_law
    monkeypatch.setattr(indian_law, 'create_script', lambda *a: [{'title':'Law','lines':['தமிழ்'] * 4}])
    render_calls = []
    monkeypatch.setattr(jobs, 'render', lambda *a: render_calls.append(a[5]) or 120)
    job = dict(id=str(uuid4()), owner='owner', date='2026-09-18', voice='ta-IN-PallaviNeural', kind='indian-law', auto_render=True, status='writing')
    assert jobs.gate.acquire(blocking=False)
    jobs.run(job, 'script')
    assert jobs.get(job['id'], 'owner')['status'] == 'complete'
    assert render_calls == ['indian-law']
    assert not jobs.gate.locked()
