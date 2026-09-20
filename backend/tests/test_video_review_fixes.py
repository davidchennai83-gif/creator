"""Regression tests for bugs found in the full code review."""
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.video_creator import backgrounds, scripts, stock_photos
from app.video_creator import render as renderer

BACKEND = Path(__file__).resolve().parents[1]
TAMIL = ['கிபி 1947 இல் முக்கிய நிகழ்வு நடந்தது.', 'இது வரலாற்றில் பெரிய மாற்றம் ஆகும்.']
OFFERED = [round(i * 99 / 29) for i in range(30)]  # candidate ids create_script sends to the model when 100 events exist


class FakeOllama:
    reply = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        request = httpx.Request('POST', 'http://ollama.test/api/chat')
        return httpx.Response(200, json={'message': {'content': json.dumps(FakeOllama.reply)}}, request=request)


@pytest.fixture
def ollama(monkeypatch):
    monkeypatch.setattr(scripts, 'get_sources', lambda day: [{'source_id': i, 'year': str(1000 + i), 'text': f'event {i}', 'links': []} for i in range(100)])
    monkeypatch.setattr(scripts.httpx, 'Client', FakeOllama)
    return FakeOllama


def reply(ids):
    return {'points': [{'source_id': i, 'lines': TAMIL} for i in ids]}


def test_script_accepts_events_the_model_was_shown(ollama):
    ollama.reply = reply(OFFERED[:10])
    points = scripts.create_script(date(2026, 9, 20), lambda message: None)
    assert [p['source_id'] for p in points] == OFFERED[:10]


def test_script_rejects_event_the_model_was_never_shown(ollama):
    hidden = next(i for i in range(100) if i not in OFFERED)
    ollama.reply = reply(OFFERED[:9] + [hidden])
    with pytest.raises(ValueError, match='invalid or repeated'):
        scripts.create_script(date(2026, 9, 20), lambda message: None)


def test_frame_renderer_failure_reports_the_real_reason(monkeypatch, tmp_path):
    failed = subprocess.CompletedProcess(['node'], 1, stdout='', stderr='Error: Tamil summary is too long for the frame')
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: failed)
    with pytest.raises(RuntimeError, match='Tamil summary is too long'):
        renderer.render_frames(tmp_path)


def test_render_explains_missing_video_packages(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'moviepy', None)
    with pytest.raises(RuntimeError, match='requirements-video.txt'):
        renderer.render([], tmp_path, '2026-09-20', 'ta-IN-PallaviNeural', lambda message: None)


def test_api_imports_without_optional_video_packages(tmp_path):
    """The Docker image installs requirements.txt only; the API must still start."""
    code = "import sys\nfor m in ('moviepy','edge_tts','PIL','numpy'): sys.modules[m] = None\nimport app.main"
    env = dict(os.environ, DATABASE_URL=f"sqlite+aiosqlite:///{(tmp_path / 'x.db').as_posix()}")
    result = subprocess.run([sys.executable, '-c', code], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('text,topic', [
    ('King Edward VII becomes king of the United Kingdom', 'history'),
    ('Nobel Prize award ceremony held in Stockholm', 'history'),
    ('Leadership of the church passes to a new pope; worship resumes', 'history'),
    ('Citizenship rights extended; Limited Liability Partnership formed', 'justice'),
    ('World War II begins with the invasion of Poland', 'conflict'),
    ('The ship Titanic sinks in the North Atlantic', 'maritime'),
    ('The warship HMS Dreadnought is launched', 'maritime'),
    ('Sailing expedition of Magellan sets sail', 'maritime'),
])
def test_illustration_topics_match_whole_words(text, topic):
    assert backgrounds.illustration({'text': text}, 'history', 0)['topic'] == topic


def test_education_act_gets_a_school_photo_but_child_abuse_law_stays_neutral():
    education = {'title': 'Right of Children to Free and Compulsory Education Act, 2009'}
    pocso = {'title': 'Protection of Children from Sexual Offences Act, 2012'}
    assert stock_photos.query_for(education, 'indian-law', 'education') == 'library books'
    assert stock_photos.query_for(pocso, 'indian-law', 'family') == 'courthouse building'
