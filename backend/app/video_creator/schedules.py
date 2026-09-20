"""Durable single-PC schedules. Times use Asia/Kolkata; social destinations are intent only."""
import calendar
import json
import logging
import sqlite3
import threading
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, model_validator
from . import jobs

IST = timezone(timedelta(hours=5, minutes=30))
PROJECTS = [{'id': 'history', 'name': 'Day of History', 'description': '10 historical events · Tamil narration'},
            {'id': 'indian-law', 'name': 'Indian Law — Daily 5 Acts', 'description': '5 Acts · 4 Tamil lines each'}]


def now():
    return datetime.now(IST)


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    project: Literal['history', 'indian-law']
    run_time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    frequency: Literal['daily', 'weekly', 'monthly', 'custom']
    start_date: date
    end_date: date
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    month_day: int = Field(default=1, ge=1, le=31)
    interval_days: int = Field(default=2, ge=1, le=365)
    platforms: list[Literal['youtube', 'facebook', 'instagram']] = Field(default_factory=list, max_length=3)
    voice: Literal['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural'] = 'ta-IN-PallaviNeural'

    @model_validator(mode='after')
    def validate_range(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError('Task name cannot be empty')
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


def connect():
    db = sqlite3.connect(jobs.root() / 'schedules.sqlite3', timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)')
    return db


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
        task.update(id=str(task_id or uuid4()), owner=str(owner), enabled=True, next_run=upcoming,
                    timezone='Asia/Kolkata', publishing_status='connection_required' if body['platforms'] else 'gallery_only',
                    message='Scheduled', updated_at=now().isoformat())
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
