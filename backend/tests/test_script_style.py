"""One spoken register for every show: subject first, talk to the viewer, no filler.

These tests are the guard for the house style in ``app/video_creator/style.py``.
They cover the curated catalogues (the data), the composed law/money scripts and
the model prompt that writes the history narration.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.video_creator import style
from app.video_creator.daily_catalog import build_points, load_catalog
from app.video_creator.indian_law import create_script as law_script
from app.video_creator.make_money import create_script as money_script
from app.video_creator.meesho.ai_copy import build_prompt

VIDEO_DIR = Path(__file__).resolve().parents[1] / 'app' / 'video_creator'
CATALOGUE_KINDS = ('health', 'motivation', 'kids', 'gk', 'english', 'thirukkural')
PER_DAY = {'thirukkural': 2}
DAY = date(2026, 11, 20)


def test_style_flags_the_old_fillers_and_the_trailing_tic():
    assert style.breaches('ஒரு நிமிஷம் யோசிச்சு பாருங்க, இது ஒரு சட்டம்.')
    assert style.breaches('இதுக்கு பின்னாடி இருக்குற உண்மை, இது ஒரு வழி.')
    assert style.breaches('இன்றைய உடல்நல குறிப்பு: தண்ணீர்.')
    assert style.breaches('இது ஒரு நல்ல விஷயம், பாருங்க.')
    assert style.breaches('இது ஒரு நல்ல விஷயம், பாருங்க!')
    assert style.breaches('தண்ணீர் குடிக்கிறது பத்தி இன்னைக்கு பேசலாம்.') is None
    # "பாருங்க" inside a sentence is ordinary Tamil, only the sentence-final tic is banned.
    assert style.breaches('அவர் பாருங்க என்று சொல்லி விளாசினார்.') is None


def test_every_curated_line_follows_the_house_style():
    for kind in CATALOGUE_KINDS:
        for item in load_catalog(VIDEO_DIR / kind):
            for line in item['lines']:
                assert style.breaches(line) is None, (kind, item['id'], line)
    for name, path in (('indian_law', VIDEO_DIR / 'indian_law' / 'tamil.json'),
                       ('make_money', VIDEO_DIR / 'make_money' / 'tamil.json')):
        for key, lines in json.loads(path.read_text(encoding='utf-8')).items():
            for line in lines:
                assert style.breaches(line) is None, (name, key, line)


def test_a_shared_closing_line_is_spoken_once_per_video():
    items = load_catalog(VIDEO_DIR / 'health')
    points = build_points(items, DAY, 3)
    closing = items[0]['lines'][-1]
    assert points[-1]['lines'][-1] == closing
    assert all(closing not in point['lines'] for point in points[:-1])


@pytest.mark.parametrize('kind', CATALOGUE_KINDS)
def test_daily_scripts_stay_clean(kind):
    items = load_catalog(VIDEO_DIR / kind)
    for offset in range(3):
        for point in build_points(items, DAY + timedelta(days=offset), PER_DAY.get(kind, 3)):
            for line in point['lines']:
                assert style.breaches(line) is None, (kind, point['title'], line)


def test_law_and_money_scripts_stay_clean():
    for create in (law_script, money_script):
        for point in create(DAY, lambda message: None):
            assert style.check(point['lines'], point['title'])
            for line in point['lines']:
                assert style.breaches(line) is None, line


def test_the_meesho_prompt_carries_the_same_rule():
    prompt = build_prompt({'title': 'Steel bottle', 'title_ta': 'ஸ்டீல் பாட்டில்'})
    assert 'பாருங்க' in prompt and 'stock filler' in prompt
