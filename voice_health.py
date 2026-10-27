"""Watchdog helper: is the 24x7 voice agent healthy, and is it safe to restart the backend?

Prints one word:
  OK       - heartbeat file exists and is fresh
  RESTART  - heartbeat is stale and no video job is mid-render, so a restart is safe
  WAIT     - heartbeat is stale but a render/script job is active, do not restart
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "backend" / "storage"
STALE_SECONDS = 20 * 60


def main() -> int:
    state = STORAGE / "voice" / "state.json"
    if state.is_file() and (time.time() - state.stat().st_mtime) < STALE_SECONDS:
        print("OK")
        return 0
    jobs_db = STORAGE / "video_creator" / "jobs.sqlite3"
    active = False
    if jobs_db.is_file():
        try:
            with sqlite3.connect(str(jobs_db), timeout=10) as db:
                for (body,) in db.execute("SELECT body FROM jobs").fetchall():
                    try:
                        if json.loads(body).get("status") in ("writing", "rendering"):
                            active = True
                            break
                    except Exception:
                        continue
        except Exception:
            active = False
    print("WAIT" if active else "RESTART")
    return 0


if __name__ == "__main__":
    sys.exit(main())
