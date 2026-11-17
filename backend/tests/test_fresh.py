import json
import sqlite3
import time
from pathlib import Path

import pytest

from app.video_creator import fresh


@pytest.fixture
def storage(monkeypatch, tmp_path):
    monkeypatch.setattr(fresh.settings, 'STORAGE_PATH', str(tmp_path))
    monkeypatch.setattr(fresh.settings, 'STOCK_REUSE_DAYS', 21)
    return tmp_path


def test_remember_and_recent(storage):
    fresh.remember('photo', [101, 'pexels-2'])
    seen = fresh.recent('photo')
    assert seen == {'101', 'pexels-2'}
    assert fresh.recent('video') == set()


def test_window_can_be_disabled(storage, monkeypatch):
    fresh.remember('video', [7])
    monkeypatch.setattr(fresh.settings, 'STOCK_REUSE_DAYS', 0)
    assert fresh.recent('video') == set()


def test_old_entries_fall_out_of_the_window(storage, monkeypatch):
    fresh.remember('photo', [1], when=time.time() - 30 * 86400)
    assert fresh.recent('photo') == set()
    monkeypatch.setattr(fresh.settings, 'STOCK_REUSE_DAYS', 60)
    assert fresh.recent('photo') == {'1'}


def test_corrupt_file_only_costs_freshness(storage):
    (storage / 'video_creator').mkdir(parents=True, exist_ok=True)
    (storage / 'video_creator' / 'used-media.json').write_text('{not json', encoding='utf-8')
    assert fresh.recent('photo') == set()
    fresh.remember('photo', [5])
    assert fresh.recent('photo') == {'5'}


def test_first_run_seeds_from_finished_jobs(storage):
    folder = storage / 'video_creator'
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / 'jobs.sqlite3')
    db.execute('create table jobs (body text)')
    body = json.dumps({'date': time.strftime('%Y-%m-%d'),
                       'media_sources': [{'photo_id': 11}, {'video_id': 22},
                                         {'commons_id': 'commons-33'}]})
    db.execute('insert into jobs values (?)', (body,))
    db.commit()
    db.close()

    assert fresh.recent('video') == {'22'}
    assert fresh.recent('photo') == {'11', 'commons-33'}
