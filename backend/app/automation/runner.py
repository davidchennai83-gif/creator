"""Run Playwright automation projects as subprocesses, one at a time, owner-isolated records."""
import json
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from uuid import uuid4

from app.config.settings import settings
from . import store

gate = threading.Lock()
log = logging.getLogger(__name__)

# YouTube uploads deliberately wait 15 minutes between confirmed videos. A
# normal day (10 videos) already takes over two hours, and a missed-day backlog
# can double that, so the global one-hour automation limit would kill a healthy
# YouTube run. Other projects keep the configured limit.
YOUTUBE_RUN_TIMEOUT = 8 * 60 * 60

# User scripts run as subprocesses, so they receive a strict environment allowlist:
# signing keys, database URLs and provider credentials never reach automation code.
ALLOWED_ENV_KEYS = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR", "TEMP", "TMP",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "LANG", "LC_ALL", "LANGUAGE",
    "PYTHONUTF8", "PYTHONIOENCODING", "VIRTUAL_ENV", "PLAYWRIGHT_BROWSERS_PATH",
})


def _script_env(project_dir: Path) -> dict:
    env = {key: value for key, value in os.environ.items() if key.upper() in ALLOWED_ENV_KEYS}
    env["AUTOMATION_PATH"] = str(root())
    env["AUTOMATION_PROJECT"] = str(project_dir)
    env["PYTHONUTF8"] = "1"
    return env


def _kill_tree(proc) -> None:
    """Stop the script and any browser/driver processes it spawned."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def root() -> Path:
    return Path(settings.AUTOMATION_PATH)


def connect():
    """Return a usable runs DB connection. The dying system disk sometimes corrupts
    this sqlite file, which used to crash the whole scheduler tick; self-heal instead."""
    db_path = root() / "runs.sqlite3"
    try:
        db = sqlite3.connect(str(db_path), timeout=30)
        db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)')
        return db
    except sqlite3.DatabaseError:
        log.warning('runs.sqlite3 is malformed — recreating a fresh run database')
        try:
            db.close()
        except Exception:
            pass
        try:
            import shutil
            import time
            backup = db_path.with_name(f"runs.sqlite3.malformed.{int(time.time())}.bak")
            shutil.copy2(str(db_path), str(backup))
        except Exception:
            pass
        try:
            db_path.unlink()
        except Exception:
            pass
        db = sqlite3.connect(str(db_path), timeout=30)
        db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)')
        return db


def save(run):
    try:
        with connect() as db:
            db.execute('INSERT OR REPLACE INTO runs VALUES (?,?,?)', (run['id'], run['owner'], json.dumps(run)))
    except Exception as exc:
        # Logging must never stop an automation run or crash the scheduler.
        log.warning('Could not persist automation run %s: %s', run.get('id'), exc)


def get(run_id, owner):
    try:
        with connect() as db:
            row = db.execute('SELECT body FROM runs WHERE id=? AND owner=?', (str(run_id), str(owner))).fetchone()
        return json.loads(row[0]) if row else None
    except Exception as exc:
        log.warning('Could not read automation run %s: %s', run_id, exc)
        return None


def listing(owner, limit=30):
    try:
        with connect() as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT body FROM runs WHERE owner=? ORDER BY rowid DESC LIMIT ?', (str(owner), limit))]
    except Exception as exc:
        log.warning('Could not list automation runs: %s', exc)
        return []


def run(owner, project, file="main.py"):
    """Start one automation run. Returns the run record; caller must hold nothing extra."""
    path = store.file_path(project, file)
    if not path.is_file():
        raise LookupError(f'Project file {file!r} was not found')
    if not gate.acquire(blocking=False):
        raise ValueError('Another automation run is running. Wait until it finishes.')
    run_id = str(uuid4())
    run = {'id': run_id, 'owner': str(owner), 'project': store.safe_project(project), 'file': path.name,
           'status': 'running', 'message': 'Starting…', 'started_at': _now(), 'finished_at': None,
           'exit_code': None, 'preview': '', 'log_file': ''}
    save(run)
    try:
        thread = threading.Thread(target=_execute, args=(run,), daemon=True)
        thread.start()
    except Exception:
        gate.release()
        save({**run, 'status': 'failed', 'message': 'Failed to start the run'})
        raise
    return run


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _execute(run):
    proc = None
    timer = None
    timed_out = False
    try:
        project_dir = store.folder(run['project'])
        log_path = root() / 'runs'
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / f"{run['id']}.log"
        command = [sys.executable, str(store.file_path(run['project'], run['file']))]
        proc = subprocess.Popen(command, cwd=str(project_dir), env=_script_env(project_dir),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding='utf-8', errors='replace', bufsize=1)

        def _on_timeout():
            nonlocal timed_out
            timed_out = True
            _kill_tree(proc)

        run_timeout = (YOUTUBE_RUN_TIMEOUT if 'youtube' in run['project'].lower()
                       else settings.AUTOMATION_RUN_TIMEOUT)
        timer = threading.Timer(run_timeout, _on_timeout)
        timer.daemon = True
        timer.start()
        chunks = []
        # Stream into the log once; readers tail it live instead of rewriting per line.
        with log_file.open('w', encoding='utf-8') as out:
            for line in proc.stdout:
                chunks.append(line)
                out.write(line)
                out.flush()
        try:
            code = proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            code = proc.wait(timeout=30)
        output = ''.join(chunks)
        if timed_out:
            run.update(exit_code=code, preview=output[-6000:], log_file=str(log_file),
                       status='failed',
                       message=f'Timed out after {run_timeout}s and was stopped',
                       finished_at=_now())
        else:
            run.update(exit_code=code, preview=output[-6000:], log_file=str(log_file),
                       status='completed' if code == 0 else 'failed',
                       message='Completed' if code == 0 else f'Failed with exit code {code}',
                       finished_at=_now())
    except Exception as exc:
        log.exception('Automation run %s failed', run['id'])
        run.update(status='failed', finished_at=_now(),
                   message=f'{type(exc).__name__}: {exc}', preview=(run.get('preview') or '') + traceback.format_exc())
    finally:
        if timer is not None:
            timer.cancel()
        if proc is not None and proc.poll() is None:
            _kill_tree(proc)
        save(run)
        gate.release()
    return run