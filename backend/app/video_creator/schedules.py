"""Durable single-PC schedules. Times use Asia/Kolkata; social destinations are intent only."""
import calendar
import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, model_validator
from . import jobs
from app.automation import runner as automation_runner
from app.automation import store as automation_store

IST = timezone(timedelta(hours=5, minutes=30))
PROJECTS = [{'id': 'history', 'name': 'Day of History', 'description': '10 historical events · Tamil narration'},
            {'id': 'indian-law', 'name': 'Indian Law — Daily 5 Acts', 'description': '5 Acts · 4 Tamil lines each'},
            {'id': 'make-money', 'name': 'How to Make Money — 5 ideas', 'description': '5 ideas · 4 Chennai-Tamil lines each'},
            {'id': 'news', 'name': 'Tamil News — Daily 10', 'description': '10 Tamil news stories · RSS images · source credits'},
            {'id': 'thirukkural', 'name': 'Thirukkural — Daily 2 Couplets', 'description': '2 couplets · Tamil meaning · 540-day cycle'},
            {'id': 'english', 'name': 'Spoken English — Daily Phrases', 'description': '3 phrases · Tamil meaning · 1,140-day cycle'},
            {'id': 'gk', 'name': 'Amazing Facts — Daily GK', 'description': '3 facts · spoken Tamil · 1,140-day cycle'},
            {'id': 'health', 'name': 'Health Tips — Daily 3', 'description': '3 safe wellbeing tips · 1,140-day cycle'},
            {'id': 'motivation', 'name': 'Life Lessons — Daily 3', 'description': '3 positive Tamil lessons · 1,140-day cycle'},
            {'id': 'kids', 'name': 'Kids Learning — Daily 3', 'description': '3 Tamil basics for kids · 7,140-day cycle'},
            {'id': 'meesho', 'name': 'Tamil Budget Finds — Daily Product', 'description': '1 Meesho budget product · price · benefits · honest caution · CTA'}]


def now():
    return datetime.now(IST)


AUTOMATION_PREFIX = 'automation:'


def project_kind(project):
    return 'automation' if project.startswith(AUTOMATION_PREFIX) else 'video'


def validate_project(project):
    if project.startswith(AUTOMATION_PREFIX):
        if not automation_store.exists(project[len(AUTOMATION_PREFIX):]):
            raise ValueError('Unknown automation project')
        return project
    if project in {p['id'] for p in PROJECTS}:
        return project
    raise ValueError('Unknown project')


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    project: str = Field(min_length=1, max_length=100)
    run_time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    frequency: Literal['daily', 'weekly', 'monthly', 'custom']
    start_date: date
    end_date: date
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    month_day: int = Field(default=1, ge=1, le=31)
    interval_days: int = Field(default=2, ge=1, le=365)
    platforms: list[Literal['youtube', 'facebook', 'instagram']] = Field(default_factory=list, max_length=3)
    voice: Literal['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural', 'ta-LK-KumarNeural', 'ta-LK-SaranyaNeural', 'ta-MY-KaniNeural', 'ta-MY-SuryaNeural', 'ta-SG-AnbuNeural', 'ta-SG-VenbaNeural'] = 'ta-IN-PallaviNeural'

    @model_validator(mode='after')
    def validate_range(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError('Task name cannot be empty')
        validate_project(self.project)
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 3660:
            raise ValueError('Choose an end date after the start date, within ten years')
        if any(d < 0 or d > 6 for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError('Weekdays must be unique values from Monday (0) to Sunday (6)')
        if self.frequency == 'weekly' and not self.weekdays:
            raise ValueError('Select at least one weekday')
        if len(set(self.platforms)) != len(self.platforms):
            raise ValueError('Choose each platform once')
        return self


def next_run(data, after):
    start, end = date.fromisoformat(data['start_date']), date.fromisoformat(data['end_date'])
    day = max(start, after.astimezone(IST).date())
    hour, minute = map(int, data['run_time'].split(':'))
    while day <= end:
        freq = data['frequency']
        match = (freq == 'daily' or (freq == 'weekly' and day.weekday() in data['weekdays'])
                 or (freq == 'monthly' and day.day == min(data['month_day'], calendar.monthrange(day.year, day.month)[1]))
                 or (freq == 'custom' and (day - start).days % data['interval_days'] == 0))
        candidate = datetime.combine(day, time(hour, minute), IST)
        if match and candidate > after:
            return candidate.isoformat()
        day += timedelta(days=1)
    return None


@contextmanager
def connect():
    db = sqlite3.connect(jobs.root() / 'schedules.sqlite3', timeout=30)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        # Committing does not release the file handle; close it so tests and
        # backup/restore tooling can remove or replace the database.
        db.close()


def save(db, task):
    db.execute('INSERT OR REPLACE INTO schedules VALUES (?,?,?)', (task['id'], task['owner'], json.dumps(task)))


def listing(owner):
    with connect() as db:
        tasks = [json.loads(row[0]) for row in db.execute('SELECT body FROM schedules WHERE owner=? ORDER BY rowid DESC', (str(owner),))]
    for task in tasks:
        job = jobs.get(task.get('last_job_id', ''), owner)
        task['last_job_status'] = job['status'] if job else None
        task['last_job_message'] = job.get('message') if job else None
    return tasks


def put(owner, data, task_id=None):
    body = data.model_dump(mode='json')
    upcoming = next_run(body, now())
    if not upcoming:
        raise ValueError('No future run in this date range. Choose a later time or end date.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        previous = None
        if task_id:
            row = db.execute('SELECT body FROM schedules WHERE id=? AND owner=?', (str(task_id), str(owner))).fetchone()
            if not row:
                raise LookupError('Task not found')
            previous = json.loads(row[0])
        task = dict(previous or {}, **body)
        # Editing a paused task must not silently resume it.
        enabled = previous.get('enabled', True) if previous else True
        task.update(id=str(task_id or uuid4()), owner=str(owner), enabled=enabled, next_run=upcoming,
                    timezone='Asia/Kolkata', publishing_status='connection_required' if body['platforms'] else 'gallery_only',
                    message='Scheduled' if enabled else 'Paused', updated_at=now().isoformat())
        save(db, task)
    return task


def change(owner, task_id, action):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT body FROM schedules WHERE id=? AND owner=?', (str(task_id), str(owner))).fetchone()
        if not row:
            raise LookupError('Task not found')
        task = json.loads(row[0])
        if action == 'delete':
            db.execute('DELETE FROM schedules WHERE id=? AND owner=?', (str(task_id), str(owner)))
            return {'deleted': True}
        task['enabled'] = action == 'resume'
        if task['enabled']:
            task['next_run'] = next_run(task, now())
            if not task['next_run']:
                raise ValueError('Date range has ended. Edit the task before resuming.')
        task['message'] = 'Scheduled' if task['enabled'] else 'Paused'
        save(db, task)
        return task


def owner_allowed(owner):
    from sqlalchemy import select
    from app.database.engine import sync_engine
    from app.models.user import User
    from uuid import UUID
    with sync_engine.connect() as db:
        row = db.execute(select(User.is_active, User.role).where(User.id == UUID(owner))).first()
    return bool(row and row.is_active and row.role.value in ('SUPER_ADMIN', 'ADMIN', 'EDITOR'))


def tick(current=None):
    current = current or now()
    with connect() as db:
        # Serializes schedule edits/claims across workers. Video jobs use a different database.
        db.execute('BEGIN IMMEDIATE')
        for (body,) in db.execute('SELECT body FROM schedules').fetchall():
            task = json.loads(body)
            if not task['enabled'] or not task['next_run'] or datetime.fromisoformat(task['next_run']) > current:
                continue
            if not owner_allowed(task['owner']):
                task.update(enabled=False, message='Paused: account is unavailable or cannot generate videos')
            elif date.fromisoformat(task['end_date']) < current.date():
                task.update(next_run=None, message='Date range completed')
            else:
                # Skip missed prior days; never generate a backlog after PC sleep/restart.
                due = datetime.fromisoformat(task['next_run'])
                if due.date() < current.date():
                    task['next_run'] = next_run(task, datetime.combine(current.date(), time.min, IST) - timedelta(microseconds=1))
                    if not task['next_run'] or datetime.fromisoformat(task['next_run']) > current:
                        save(db, task)
                        continue
                if project_kind(task['project']) == 'automation':
                    # Playwright automation tasks run locally as a subprocess; video
                    # jobs and automation runs use separate gates on this single PC.
                    project = task['project'][len(AUTOMATION_PREFIX):]
                    last = task.get('last_automation_run')
                    if last:
                        try:
                            last_run_rec = automation_runner.get(str(last), task['owner'])
                        except Exception:
                            # A corrupt run log must never abort the scheduler tick.
                            last_run_rec = None
                        if last_run_rec and last_run_rec['status'] in ('completed', 'failed'):
                            task['message'] = f"Automation: {last_run_rec['status']}{' (' + str(last_run_rec['exit_code']) + ')' if last_run_rec['exit_code'] is not None else ''}"
                    if automation_runner.gate.locked():
                        task['message'] = 'Waiting for the current automation run'
                    else:
                        try:
                            run = automation_runner.run(task['owner'], project, 'main.py')
                        except Exception as exc:
                            task['message'] = f'Automation: {exc}'
                        else:
                            task.update(last_automation_run=run['id'], last_run=current.isoformat(),
                                        message='Automation run started', next_run=next_run(task, current))
                    save(db, task)
                    continue
                if jobs.gate.locked():
                    task['message'] = 'Waiting for the current video to finish'
                else:
                    # Deterministic ID makes restart between job creation and schedule commit idempotent.
                    from uuid import uuid5, NAMESPACE_URL
                    job_id = str(uuid5(NAMESPACE_URL, task['id'] + ':' + task['next_run']))
                    existing = jobs.get(job_id, task['owner'])
                    try:
                        job = existing or jobs.new(task['owner'], current.date(), task['voice'], task['project'], auto_render=True, job_id=job_id)
                        task.update(last_job_id=job['id'], last_run=current.isoformat(), message='Video generation started',
                                    next_run=next_run(task, current))
                    except ValueError:
                        task['message'] = 'Waiting for the current video to finish'
            save(db, task)


def start_worker():
    stop = threading.Event()
    def work():
        while not stop.is_set():
            try:
                tick()
            except Exception:
                logging.getLogger(__name__).exception('Scheduler tick failed')
            stop.wait(20)
    thread = threading.Thread(target=work, name='video-scheduler', daemon=True)
    thread.start()
    return stop, thread
