"""Watchdog helper for applying an autonomous self-upgrade.

Prints one word:
  OK    - no video job is mid-render and no upload is running, so restarting the backend is safe
  WAIT  - a render / script / upload job is active, defer the restart
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "backend" / "storage"


def _active_video_job() -> bool:
    db_path = STORAGE / "video_creator" / "jobs.sqlite3"
    if not db_path.is_file():
        return False
    try:
        with sqlite3.connect(str(db_path), timeout=10) as db:
            for (body,) in db.execute("SELECT body FROM jobs").fetchall():
                try:
                    if json.loads(body).get("status") in ("writing", "rendering"):
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def _active_upload_run() -> bool:
    db_path = STORAGE / "automation" / "runs.sqlite3"
    if not db_path.is_file():
        return False
    try:
        with sqlite3.connect(str(db_path), timeout=10) as db:
            for (body,) in db.execute("SELECT body FROM runs").fetchall():
                try:
                    if json.loads(body).get("status") == "running":
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def main() -> int:
    print("WAIT" if (_active_video_job() or _active_upload_run()) else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
