from datetime import date, timedelta
import json
import pytest
import httpx
from pydantic import ValidationError
from app.video_creator.indian_law import LawScript, create_script, daily_acts
from app.video_creator.routes import Request


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
