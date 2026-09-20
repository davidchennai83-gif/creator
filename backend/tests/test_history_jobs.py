from datetime import date
import httpx
from app.video_creator import jobs


def test_timeout_preserves_stage_and_releases_worker(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    def fail(day, progress):
        progress('Writing Tamil summaries with Ollama')
        raise httpx.ReadTimeout('test timeout')
    monkeypatch.setattr(jobs, 'create_script', fail)
    job = {'id': 'timeout-test', 'owner': 'test', 'date': date.today().isoformat(), 'status': 'writing', 'message': ''}
    assert jobs.gate.acquire(blocking=False)
    jobs.run(job, 'script')
    saved = jobs.get(job['id'], 'test')
    assert saved['status'] == 'failed'
    assert 'Writing Tamil summaries' in saved['message']
    assert 'gemma3:4b' in saved['message']
    assert (tmp_path / job['id'] / 'error.log').is_file()
    assert not jobs.gate.locked()
    assert jobs.get(job['id'], 'another-owner') is None


def test_render_failure_never_claims_success(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    def fail(*args):
        raise RuntimeError('render unavailable')
    monkeypatch.setattr(jobs, 'render', fail)
    job = {'id': 'render-test', 'owner': 'test', 'date': '2026-09-17', 'voice': 'ta-IN-PallaviNeural', 'points': [], 'status': 'rendering'}
    assert jobs.gate.acquire(blocking=False)
    jobs.run(job, 'render')
    assert jobs.get(job['id'], 'test')['status'] == 'failed'
    assert not jobs.gate.locked()
