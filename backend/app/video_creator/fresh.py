"""Remember which stock assets were used, so backgrounds stay fresh.

Pexels returns the same ranked page for the same query every day, so a fixed
photo query (Thirukkural's "palm leaf manuscript", History's kind presets) used
to put the same picture in every video for weeks. This registry records the id
of each photo/video that made it into a render and lets the pickers skip ids
seen inside ``STOCK_REUSE_DAYS``. It is deliberately tiny JSON: one write per
render, best effort, and a corrupt file only costs freshness, never a video.
"""
import json
import time
from pathlib import Path

from app.config.settings import settings

KEEP_DAYS = 120


def _path():
    folder = Path(settings.STORAGE_PATH) / 'video_creator'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'used-media.json'


def _load():
    try:
        data = json.loads(_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    seeded = _seed()
    return seeded


def _seed():
    """First run: import what past videos already showed.

    Without this the registry starts empty and the first render after the upgrade
    can repeat a background the viewer saw yesterday. Job media sources already
    record every photo/video id, so the last weeks of videos seed the window.
    """
    import sqlite3

    path = _path()
    if path.exists():
        return {}
    db_path = Path(settings.STORAGE_PATH) / 'video_creator' / 'jobs.sqlite3'
    data = {}
    try:
        with sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True) as db:
            rows = db.execute('select body from jobs').fetchall()
    except sqlite3.Error:
        return data
    for (body,) in rows:
        try:
            job = json.loads(body)
        except (TypeError, ValueError):
            continue
        try:
            stamp = time.mktime(time.strptime(str(job.get('date')), '%Y-%m-%d'))
        except (TypeError, ValueError):
            continue
        for credit in job.get('media_sources') or []:
            if not isinstance(credit, dict):
                continue
            for key, kind in (('photo_id', 'photo'), ('video_id', 'video'),
                              ('commons_id', 'photo')):
                value = credit.get(key)
                if value in (None, ''):
                    continue
                slot = data.setdefault(kind, {})
                slot[str(value)] = max(float(slot.get(str(value), 0)), stamp)
    try:
        path.write_text(json.dumps(data), encoding='utf-8')
    except OSError:
        return {}
    return data


def _window():
    try:
        days = int(settings.STOCK_REUSE_DAYS)
    except (TypeError, ValueError):
        days = 21
    return max(0, days)


def recent(kind):
    """Ids of this asset kind seen inside the reuse window (empty = no limit)."""
    days = _window()
    if days <= 0:
        return set()
    cutoff = time.time() - days * 86400
    entries = _load().get(kind) or {}
    fresh = set()
    for asset_id, used in entries.items():
        try:
            if float(used) >= cutoff:
                fresh.add(str(asset_id))
        except (TypeError, ValueError):
            continue
    return fresh


def remember(kind, ids, when=None):
    """Record ids as used now, and drop entries older than KEEP_DAYS."""
    ids = [str(asset_id) for asset_id in ids if asset_id not in (None, '')]
    if not ids:
        return
    stamp = float(when if when is not None else time.time())
    data = _load()
    entries = data.get(kind) if isinstance(data.get(kind), dict) else {}
    for asset_id in ids:
        entries[asset_id] = stamp
    cutoff = stamp - KEEP_DAYS * 86400
    kept = {}
    for asset_id, used in entries.items():
        try:
            if float(used) >= cutoff:
                kept[asset_id] = used
        except (TypeError, ValueError):
            continue
    data[kind] = kept
    try:
        _path().write_text(json.dumps(data), encoding='utf-8')
    except OSError:
        pass
