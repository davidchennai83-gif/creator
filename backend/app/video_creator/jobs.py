"""Durable local job records, one render at a time, owner-isolated artifacts."""
import json
import logging
import shutil
import sqlite3
import threading
from contextlib import contextmanager
import httpx
import traceback
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from app.config.settings import settings
from .registry import KINDS, create as create_video_script, finished_message
from .render import render, cleanup_intermediates

gate = threading.Lock()
log = logging.getLogger(__name__)


def root():
    path = Path(settings.STORAGE_PATH) / 'video_creator'
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect():
    db = sqlite3.connect(root() / 'jobs.sqlite3', timeout=30)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        # sqlite3.Connection's own context manager commits but never closes;
        # without this the scheduler thread keeps the test/app DB locked.
        db.close()


def save(job):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)', (job['id'], job['owner'], json.dumps(job)))


def get(job_id, owner):
    with connect() as db:
        row = db.execute('SELECT body FROM jobs WHERE id=? AND owner=?', (str(job_id), str(owner))).fetchone()
    return json.loads(row[0]) if row else None


def listing(owner):
    with connect() as db:
        return [json.loads(r[0]) for r in db.execute('SELECT body FROM jobs WHERE owner=? ORDER BY rowid DESC LIMIT 30', (str(owner),))]


def delete(job_id, owner):
    job_id = str(UUID(str(job_id)))
    if not gate.acquire(blocking=False):
        raise ValueError('A video task is running. Delete after it finishes.')
    try:
        job = get(job_id, owner)
        if not job:
            return False
        if job['status'] in ('writing', 'rendering'):
            raise ValueError('This video is still generating. Wait until it finishes.')
        folder = root() / job_id
        if folder.exists():
            shutil.rmtree(folder)
        with connect() as db:
            db.execute('DELETE FROM jobs WHERE id=? AND owner=?', (job_id, str(owner)))
        return True
    finally:
        gate.release()


def recover():
    with connect() as db:
        for (body,) in db.execute('SELECT body FROM jobs').fetchall():
            try:
                job = json.loads(body)
            except (TypeError, ValueError):
                # One corrupt row must not prevent the whole server from starting.
                log.warning('Skipping unreadable video job record')
                continue
            if job.get('status') in ('writing', 'rendering'):
                job.update(status='failed', message='Server restarted during generation. Please create a new job.')
                db.execute('UPDATE jobs SET body=? WHERE id=?', (json.dumps(job), job['id']))
    # Sweep frame stills left over by renders that predate automatic cleanup
    # (one interrupted portrait job could hold several GB).
    for folder in root().iterdir():
        if folder.is_dir() and folder.name != 'runs':
            try:
                cleanup_intermediates(folder)
            except OSError:
                log.warning('Could not clean intermediates in %s', folder)


def launch(job, action):
    if not gate.acquire(blocking=False):
        raise ValueError('Another video task is running. Wait until it finishes.')
    if action == 'render':
        current = get(job['id'], job['owner'])
        if not current or current['status'] != 'review':
            gate.release()
            raise ValueError('Video was deleted or is no longer ready to render.')
        job = current
    previous = job.copy()
    job.update(status='writing' if action == 'script' else 'rendering', message='Starting…')
    try:
        save(job)
        thread = threading.Thread(target=run, args=(job, action), daemon=True)
        thread.start()
    except Exception:
        save(previous)
        gate.release()
        raise
    return job


def new(owner, day, voice, kind='history', auto_render=False, job_id=None,
        rate='+15%', pitch='+0Hz', volume='+0%', display='tamil'):
    if kind not in KINDS:
        raise ValueError('Unknown video template')
    job = {'id': str(job_id or uuid4()), 'owner': str(owner), 'date': day.isoformat(), 'voice': voice, 'auto_render': auto_render,
           'kind': kind, 'model': settings.HISTORY_MODEL if kind == 'history' else 'curated-tamil-v1', 'status': 'new', 'points': [], 'message': '',
           'rate': rate, 'pitch': pitch, 'volume': volume, 'display': display}
    return launch(job, 'script')


def run(job, action):
    folder = None
    def progress(message):
        job['message'] = message
        save(job)
    try:
        folder = root() / job['id']
        folder.mkdir(exist_ok=True)
        if action == 'script':
            kind = job.get('kind', 'history')
            job['points'] = create_video_script(kind, date.fromisoformat(job['date']), progress)
            if not job['points']:
                raise ValueError('The script generator returned no scenes')
            message = finished_message(kind)
            if job.get('display') == 'tanglish':
                from .tanglish import transliterate
                for p in job['points']:
                    if p.get('title'):
                        p['title_display'] = transliterate(p['title'])
                    p['lines_display'] = [transliterate(line) for line in p['lines']]
            job.update(status='review', message=message)
        if action == 'render' or job.get('auto_render'):
            job.update(status='rendering', message='Preparing video scenes')
            save(job)
            job['duration'] = render(job['points'], folder, job['date'], job['voice'], progress, job.get('kind', 'history'),
                                     job.get('rate', '+15%'), job.get('pitch', '+0Hz'), job.get('volume', '+0%'))
            sources = folder / 'media-sources.json'
            if sources.is_file():
                job['media_sources'] = json.loads(sources.read_text(encoding='utf-8'))
            subtitles = folder / 'subtitles.json'
            if subtitles.is_file():
                job['subtitles'] = json.loads(subtitles.read_text(encoding='utf-8'))
            job.update(status='complete', message='MP4 ready with narrated moving scenes and clean on-screen text')
        (folder / 'script.json').write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as exc:
        log.exception('History video job %s failed', job['id'])
        stage = job.get('message', action)
        try:
            if folder is not None:
                (folder / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        except OSError:
            pass
        if isinstance(exc, httpx.ReadTimeout):
            message = f'Timed out during: {stage}. The local model may be too large or busy. Use gemma3:4b on this PC and retry.'
        elif isinstance(exc, httpx.ConnectError):
            message = f'Connection failed during: {stage}. Check Ollama is running and the internet connection.'
        else:
            message = f'{type(exc).__name__} during: {stage}. Details saved in this job\'s error.log.'
        job.update(status='failed', message=message)
    finally:
        try:
            save(job)
        finally:
            gate.release()
