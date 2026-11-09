"""Watchdog helper for applying an autonomous self-upgrade.

Prints one word:
  OK    - no video job is mid-render and no upload is running, so restarting the backend is safe
  WAIT  - a render / script / upload job is active, defer the restart

Only *recent* work counts as active. A process kill or power cut can leave rows
marked ``rendering``/``running`` forever, and those stale rows must not block
self-upgrades for days.
"""
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "backend" / "storage"
IST = timezone(timedelta(hours=5, minutes=30))
# Uploads finish well within three hours; older "running" rows are leftovers.
UPLOAD_STALE_AFTER = timedelta(hours=3)
# A render can cross midnight, so yesterday's job still counts as active.
RENDER_DATES_BACK = 1


def _active_video_job() -> bool:
    db_path = STORAGE / "video_creator" / "jobs.sqlite3"
    if not db_path.is_file():
        return False
    today = datetime.now(IST).date()
    allowed = {
        (today - timedelta(days=offset)).isoformat()
        for offset in range(RENDER_DATES_BACK + 1)
    }
    try:
        with sqlite3.connect(str(db_path), timeout=10) as db:
            for (body,) in db.execute("SELECT body FROM jobs").fetchall():
                try:
                    job = json.loads(body)
                except Exception:
                    continue
                if job.get("status") not in ("writing", "rendering"):
                    continue
                if str(job.get("date") or "")[:10] in allowed:
                    return True
    except Exception:
        pass
    return False


def _active_upload_run() -> bool:
    db_path = STORAGE / "automation" / "runs.sqlite3"
    if not db_path.is_file():
        return False
    cutoff = datetime.now(timezone.utc) - UPLOAD_STALE_AFTER
    try:
        with sqlite3.connect(str(db_path), timeout=10) as db:
            for (body,) in db.execute("SELECT body FROM runs").fetchall():
                try:
                    run = json.loads(body)
                except Exception:
                    continue
                if run.get("status") != "running":
                    continue
                started = str(run.get("started_at") or "")
                try:
                    when = datetime.fromisoformat(started.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                if when >= cutoff:
                    return True
    except Exception:
        pass
    return False


def main() -> int:
    print("WAIT" if (_active_video_job() or _active_upload_run()) else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
