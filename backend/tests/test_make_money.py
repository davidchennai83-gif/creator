import base64
import re
import sys
from datetime import date, timedelta
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_current_user
from app.video_creator import jobs, render as renderer, routes, stock_photos
from app.video_creator.backgrounds import ART, illustration
from app.video_creator.make_money import MAX_LINE, MoneyScript, catalog, create_script, daily_ideas, tamil_lines
from app.video_creator.routes import Request
from app.video_creator.schedules import PROJECTS, ScheduleInput
from app.video_creator.tanglish import transliterate

DAY = date(2026, 9, 17)


def test_daily_selection_is_stable_rotates_and_covers_the_whole_catalog():
    selected = daily_ideas(DAY)
    assert selected == daily_ideas(DAY)
    assert len({i['id'] for i in selected}) == 5
    assert not {i['id'] for i in selected} & {i['id'] for i in daily_ideas(DAY + timedelta(days=1))}
    cycle = len(catalog()) // 5
    assert selected == daily_ideas(DAY + timedelta(days=cycle))
    assert {i['id'] for d in range(cycle) for i in daily_ideas(DAY + timedelta(days=d))} == {i['id'] for i in catalog()}
    assert len(daily_ideas(date(2025, 12, 31))) == 5  # dates before the epoch still work


def test_catalog_and_tamil_lines_are_complete_and_consistent():
    assert set(tamil_lines()) == {i['id'] for i in catalog()}
    assert len({i['id'] for i in catalog()}) == len(catalog())
    for idea in catalog():
        assert len(idea['facts']) == 4 and idea['title'] and idea['title_ta'] and idea['photo']
        assert idea['topic'] in ART and idea['topic'] in stock_photos.QUERIES, idea['id']
        assert all(l['link'].startswith('https://') for l in idea['links'])
        lines = tamil_lines()[idea['id']]
        assert len(lines) == 4
        for line in lines:
            assert re.search(r'[\u0b80-\u0bff]', line) and len(line) <= MAX_LINE
            # Digits are read unpredictably by the shared Tamil voice, same as the history/law scripts.
            assert not re.search(r'\d', line)


def test_no_guaranteed_income_or_get_rich_quick_claims():
    lakh = re.compile(r'லட்சம்|கோடி(?!ங்)')  # lakh / crore promises (not "கோடிங்" = coding)
    for idea in catalog():
        assert not any(lakh.search(line) for line in tamil_lines()[idea['id']]), idea['id']


def test_script_requires_five_ideas_four_tamil_lines_that_fit_the_frame():
    point = {'source_id': 0, 'lines': ['இது ஒரு சிறிய வழிமுறை.'] * 4}
    assert len(MoneyScript(points=[dict(point, source_id=i) for i in range(5)]).points) == 5
    with pytest.raises(ValidationError):
        MoneyScript(points=[dict(point, lines=point['lines'][:2])] * 5)
    with pytest.raises(ValidationError):
        MoneyScript(points=[dict(point, lines=['English only'] * 4)] * 5)
    with pytest.raises(ValidationError):
        MoneyScript(points=[dict(point, lines=['த' * (MAX_LINE + 1)] * 4)] * 5)
    with pytest.raises(ValidationError):
        MoneyScript(points=[dict(point)] * 4)


def test_every_daily_edition_is_complete():
    for offset in range(len(catalog()) // 5):
        day = DAY + timedelta(days=offset)
        points = create_script(day, lambda message: None)
        assert [p['title_en'] for p in points] == [i['title'] for i in daily_ideas(day)]
        assert [p['source_id'] for p in points] == list(range(5))
        assert all(len(p['lines']) == 4 and p['title'] and p['text'] and p['topic'] and p['photo_query'] and isinstance(p['links'], list)
                   for p in points)


def test_speech_applies_rate_pitch_volume_the_same_way_for_every_kind(monkeypatch, tmp_path):
    """speech() takes (text, destination, voice, rate, pitch, volume) with sane defaults, applied
    identically regardless of kind \u2014 these are the user's own voice-over controls, not a hidden
    per-kind default."""
    import inspect
    assert list(inspect.signature(renderer.speech).parameters) == ['text', 'destination', 'voice', 'rate', 'pitch', 'volume']

    calls = []

    class FakeCommunicate:
        def __init__(self, text, voice, **kwargs):
            calls.append((text, voice, kwargs))

        async def save(self, path):
            return None

    monkeypatch.setitem(sys.modules, 'edge_tts', SimpleNamespace(Communicate=FakeCommunicate))
    import asyncio
    asyncio.run(renderer.speech('முதல் வரி.. இரண்டாம் வரி.', tmp_path / 'a.mp3', 'ta-IN-ValluvarNeural'))
    assert calls[-1] == ('முதல் வரி. இரண்டாம் வரி.', 'ta-IN-ValluvarNeural', {'rate': '+15%', 'pitch': '+0Hz', 'volume': '+0%'})
    asyncio.run(renderer.speech('x', tmp_path / 'b.mp3', 'ta-IN-ValluvarNeural', '+15%', '-5Hz', '+10%'))
    assert calls[-1] == ('x.', 'ta-IN-ValluvarNeural', {'rate': '+15%', 'pitch': '-5Hz', 'volume': '+10%'})


def test_voice_over_request_fields_validate_and_default_to_faster_pace():
    req = Request(kind='make-money')
    assert (req.rate, req.pitch, req.volume, req.display) == ('+15%', '+0Hz', '+0%', 'tamil')
    assert Request(kind='make-money', rate='+15%', pitch='-5Hz', volume='+10%', display='tanglish').rate == '+15%'
    with pytest.raises(ValidationError):
        Request(kind='make-money', rate='fast')
    with pytest.raises(ValidationError):
        Request(kind='make-money', pitch='+0hz')
    with pytest.raises(ValidationError):
        Request(kind='make-money', display='english')


def test_tanglish_display_is_generated_for_every_kind_but_audio_text_stays_tamil(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)

    def immediate_launch(job, action):
        assert jobs.gate.acquire(blocking=False)
        jobs.run(job, action)
        return job

    monkeypatch.setattr(jobs, 'launch', immediate_launch)
    for kind, points in [
        ('make-money', [dict(source_id=0, title='வழி 1', lines=['ஒரு வரி.'] * 4, links=[]) for _ in range(5)]),
        ('indian-law', [dict(title='சட்டம் 1', sections='1', lines=['ஒரு வரி.'] * 4, links=[]) for _ in range(5)]),
    ]:
        module = 'make_money' if kind == 'make-money' else 'indian_law'
        monkeypatch.setattr(f'app.video_creator.{module}.create_script', lambda *a, **k: points)
        job = jobs.new('owner', DAY, 'ta-IN-PallaviNeural', kind, display='tanglish')
        assert job['status'] == 'review'
        for p in job['points']:
            assert p['lines_display'][0] != p['lines'][0]  # transliterated, not the Tamil original
            assert re.search(r'[\u0b80-\u0bff]', p['lines'][0])  # the Tamil the voice will actually read
            assert not re.search(r'[\u0b80-\u0bff]', p['lines_display'][0])  # readable in Latin script


def test_make_money_no_longer_carries_its_own_narration_or_voice_tuning():
    import app.video_creator.make_money as make_money
    assert not hasattr(make_money, 'narration')
    assert not hasattr(make_money, 'speech_style')


def test_transliteration_is_readable_latin_script_and_passes_through_non_tamil():
    assert transliterate('செலவை கட்டுப்படுத்துவது முக்கியம்.') == 'Chelavai kattuppatuththuvathu mukkiyam.'
    assert transliterate('Instagram page 2026') == 'Instagram page 2026'  # already Latin/digits: untouched
    mixed = transliterate('ஆனா இங்கதான் ஒரு interesting விஷயம் இருக்கு.')
    assert 'interesting' in mixed and not re.search(r'[\u0b80-\u0bff]', mixed)
    for idea in catalog():
        for line in tamil_lines()[idea['id']]:
            out = transliterate(line)
            assert out and not re.search(r'[\u0b80-\u0bff]', out)


def test_no_dangling_vowel_signs_in_curated_tamil_content():
    """A Tamil dependent vowel sign must always attach to a Tamil consonant/vowel before it \u2014
    catches authoring slips like an English word accidentally glued to a stray matra."""
    import json
    from pathlib import Path
    law_tamil_lines = json.loads((Path(jobs.__file__).parent / 'indian_law' / 'tamil.json').read_text(encoding='utf-8'))
    vowel_signs = set('\u0bbe\u0bbf\u0bc0\u0bc1\u0bc2\u0bc6\u0bc7\u0bc8\u0bca\u0bcb\u0bcc\u0bcd')
    ok_before = set('\u0b85\u0b86\u0b87\u0b88\u0b89\u0b8a\u0b8e\u0b8f\u0b90\u0b92\u0b93\u0b94'
                     '\u0b95\u0b99\u0b9a\u0b9c\u0b9e\u0b9f\u0ba3\u0ba4\u0ba8\u0ba9\u0baa\u0bae'
                     '\u0baf\u0bb0\u0bb1\u0bb2\u0bb3\u0bb4\u0bb5\u0bb7\u0bb8\u0bb9')
    for source in (tamil_lines(), law_tamil_lines):
        for lines in source.values():
            for line in lines:
                for i, ch in enumerate(line):
                    if ch in vowel_signs:
                        assert i > 0 and line[i - 1] in ok_before, (line, i, ch)


def test_all_topics_have_valid_local_icons_and_unknown_topics_fall_back():
    for idea in catalog():
        result = illustration({'title': idea['title_ta'], 'text': ' '.join(idea['facts']), 'topic': idea['topic']}, 'make-money', 0)
        assert result['topic'] == idea['topic']
        svg = ElementTree.fromstring(base64.b64decode(result['image'].split(',', 1)[1]))
        assert svg.attrib['viewBox'] == '0 0 1080 1920'
    assert illustration({'title': 'x', 'text': 'x', 'topic': 'no-such-icon'}, 'make-money', 0)['topic'] == 'coin'
    assert illustration({'title': 'Apollo moon landing', 'text': ''}, 'history', 0)['topic'] == 'space'  # unchanged


def test_photo_query_uses_curated_object_queries_for_make_money():
    assert stock_photos.query_for({'photo_query': 'south indian food meals'}, 'make-money', 'food') == 'south indian food meals'
    assert stock_photos.query_for({}, 'make-money', 'warning') == stock_photos.QUERIES['warning']
    for idea in catalog():
        query = stock_photos.query_for({'photo_query': idea['photo']}, 'make-money', idea['topic'])
        assert not re.search(r'\b(man|woman|girl|boy|victim|person|people)\b', query), idea['id']


def test_request_scheduler_and_project_list_accept_the_new_kind():
    assert Request(kind='make-money').kind == 'make-money'
    with pytest.raises(ValidationError):
        Request(kind='make-cash')
    assert 'make-money' in {p['id'] for p in PROJECTS}
    task = ScheduleInput(name='Money tips', project='make-money', run_time='08:00', frequency='daily',
                         start_date='2026-09-22', end_date='2026-10-31')
    assert task.project == 'make-money'


def test_new_job_rejects_unknown_templates_and_labels_make_money_as_curated(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    monkeypatch.setattr(jobs, 'launch', lambda job, action: job)
    assert jobs.new('o', DAY, 'ta-IN-PallaviNeural', 'make-money')['model'] == 'curated-tamil-v1'
    with pytest.raises(ValueError, match='Unknown video template'):
        jobs.new('o', DAY, 'ta-IN-PallaviNeural', 'make-cash')


def test_download_uses_make_money_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, 'root', lambda: tmp_path)
    app = FastAPI()
    app.include_router(routes.router, prefix='/video-creator')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id='owner')
    job = dict(id='7f4c0a52-1b7e-4c1e-9c39-0d6b6b6d3a10', owner='owner', status='complete', kind='make-money', date='2026-09-17')
    jobs.save(job)
    (tmp_path / job['id']).mkdir()
    (tmp_path / job['id'] / 'history.mp4').write_bytes(b'video')
    with TestClient(app) as client:
        response = client.get(f"/video-creator/jobs/{job['id']}/download")
    assert response.status_code == 200
    assert 'make-money-2026-09-17.mp4' in response.headers['content-disposition']
