from datetime import date, timedelta
import json
from pathlib import Path

import pytest
import httpx
from pydantic import ValidationError
from app.video_creator.indian_law import MAX_LINE, LawScript, create_script, daily_acts, opening_line
from app.video_creator.routes import Request

HERE = Path(__file__).resolve().parents[1] / 'app' / 'video_creator' / 'indian_law'
FILLER = ('ஒரு நிமிஷம் யோசிச்சு பாருங்க', 'இதுக்கு பின்னாடி இருக்குற', 'இங்கதான் ஒரு')


def test_daily_selection_is_stable_and_rotates():
    day = date(2026, 9, 17)
    selected = daily_acts(day)
    assert selected == daily_acts(day)
    assert len({a['id'] for a in selected}) == 5
    assert not {a['id'] for a in selected} & {a['id'] for a in daily_acts(day + timedelta(days=1))}
    assert selected == daily_acts(day + timedelta(days=3))
    assert all(len(a['facts']) == 4 and a['sections'] for a in selected)


def test_law_script_requires_five_acts_and_four_tamil_lines():
    point = {'source_id': 0, 'lines': ['இது சட்டத்தின் விளக்கம்.'] * 4}
    assert len(LawScript(points=[dict(point, source_id=i) for i in range(5)]).points) == 5
    with pytest.raises(ValidationError):
        LawScript(points=[dict(point, lines=point['lines'][:2])] * 5)
    with pytest.raises(ValidationError):
        LawScript(points=[dict(point, lines=['English only'] * 4)] * 5)


def test_old_requests_remain_history_and_unknown_kind_is_rejected():
    assert Request().kind == 'history'
    assert Request(kind='indian-law').kind == 'indian-law'
    with pytest.raises(ValidationError):
        Request(kind='unknown')


def test_all_daily_editions_have_complete_tamil_and_citations():
    for offset in range(3):
        day = date(2026, 9, 17) + timedelta(days=offset)
        points = create_script(day, lambda message: None)
        assert [p['title'] for p in points] == [a['title'] for a in daily_acts(day)]
        assert [p['source_id'] for p in points] == list(range(5))
        assert all(len(p['lines']) == 4 and p['sections'] and p['links'] for p in points)


def test_every_act_is_named_before_anything_is_said_about_it():
    acts = json.loads((HERE / 'catalog.json').read_text(encoding='utf-8'))
    tamil = json.loads((HERE / 'tamil.json').read_text(encoding='utf-8'))
    for act in acts:
        line = opening_line(act, tamil[act['id']])
        assert line.startswith(f'{act["title_ta"]}, {act["year"]} — '), act['id']
        assert len(line) <= MAX_LINE, act['id']


def test_narration_has_no_filler_openers_or_trailing_parunga():
    acts = json.loads((HERE / 'catalog.json').read_text(encoding='utf-8'))
    tamil = json.loads((HERE / 'tamil.json').read_text(encoding='utf-8'))
    for act in acts:
        for text in [opening_line(act, tamil[act['id']])] + tamil[act['id']][1:]:
            assert not any(text.startswith(filler) for filler in FILLER), text
            assert not text.rstrip(' .').endswith('பாருங்க'), text


def test_composed_opening_line_longer_than_the_frame_is_rejected():
    act = {'id': 'x', 'title_ta': 'த' * MAX_LINE, 'year': '2000'}
    with pytest.raises(ValueError, match='opening line'):
        opening_line(act, ['இது சட்டத்தின் விளக்கம்.'])
