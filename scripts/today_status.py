"""Print today's video render and upload status in a fast, ASCII-only format.

The storage JSON payloads make ad-hoc SQL awkward, so this script parses the
two SQLite stores directly:

  backend/storage/video_creator/schedules.sqlite3  (rows: id, owner, body)
  backend/storage/video_creator/jobs.sqlite3       (rows: id, owner, body)

Usage:
    python scripts/today_status.py
    python scripts/today_status.py --date 2026-11-05
    python scripts/today_status.py --short
    python scripts/today_status.py --json

The console on this PC is cp1252, therefore every string printed here is ASCII.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "backend" / "storage" / "video_creator"
SCHEDULES_DB = STORE / "schedules.sqlite3"
JOBS_DB = STORE / "jobs.sqlite3"
RUNS_DB = ROOT / "backend" / "storage" / "automation" / "runs.sqlite3"
IST = timezone(timedelta(hours=5, minutes=30))

# Job status -> short label shown to the user.
STATUS_LABEL = {
    "complete": "done",
    "rendering": "rendering",
    "queued": "queued",
    "review": "needs review",
    "failed": "failed",
    "cancelled": "cancelled",
}

UPLOAD_MARK = "automation:"


def read_bodies(path: Path, table: str) -> list[dict]:
    if not path.exists():
        return []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = [row[0] for row in conn.execute(f"SELECT body FROM {table}")]
    finally:
        conn.close()
    out = []
    for raw in rows:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def parse_date(value: str | None) -> date:
    if not value:
        return datetime.now().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def within_window(row: dict, day: date) -> bool:
    start = str(row.get("start_date") or "")[:10]
    end = str(row.get("end_date") or "")[:10]
    if start and day < datetime.strptime(start, "%Y-%m-%d").date():
        return False
    if end and day > datetime.strptime(end, "%Y-%m-%d").date():
        return False
    return True


def runs_on(row: dict, day: date) -> bool:
    """Return True when this schedule is due on `day`.

    The scheduler treats `interval_days` as legacy metadata and runs `daily`
    schedules every day, so only the frequency and date window matter here.
    """
    frequency = str(row.get("frequency") or "daily").lower()
    if frequency == "daily":
        return True
    next_run = str(row.get("next_run") or "")[:10]
    return bool(next_run) and next_run == day.isoformat()


def hhmm(row: dict) -> str:
    return str(row.get("run_time") or "00:00")[:5]


def build_report(day: date) -> dict:
    schedules = read_bodies(SCHEDULES_DB, "schedules")
    jobs = read_bodies(JOBS_DB, "jobs")
    runs = read_bodies(RUNS_DB, "runs")

    active = [
        row for row in schedules
        if row.get("enabled", True) and within_window(row, day) and runs_on(row, day)
    ]
    active.sort(key=hhmm)

    # Latest job per project for the requested day.
    latest: dict[str, dict] = {}
    for job in jobs:
        if str(job.get("date") or "")[:10] != day.isoformat():
            continue
        kind = str(job.get("kind") or "unknown")
        latest[kind] = job  # rows are chronological; last one wins

    renders = [row for row in active if not str(row.get("project") or "").startswith(UPLOAD_MARK)]
    uploads = [row for row in active if str(row.get("project") or "").startswith(UPLOAD_MARK)]

    # Latest automation run per project for the requested day (timestamps are UTC).
    latest_run: dict[str, dict] = {}
    for run in runs:
        started = str(run.get("started_at") or "")
        try:
            local = datetime.fromisoformat(started.replace("Z", "+00:00")).astimezone(IST)
        except ValueError:
            continue
        if local.date() != day:
            continue
        project = str(run.get("project") or "")
        if not project:
            continue
        current = latest_run.get(project)
        if current is None or started > str(current.get("started_at") or ""):
            latest_run[project] = run

    def render_row(row: dict) -> dict:
        project = str(row.get("project") or "")
        job = latest.get(project)
        status = STATUS_LABEL.get(str((job or {}).get("status")), "not started")
        return {
            "time": hhmm(row),
            "project": project,
            "name": row.get("name") or project,
            "status": status,
            "job_status": (job or {}).get("status"),
        }

    def upload_row(row: dict) -> dict:
        project = str(row.get("project") or "")
        label = project[len(UPLOAD_MARK):]
        run = latest_run.get(label)
        run_status = str((run or {}).get("status") or "")
        status = {
            "completed": "done",
            "running": "running",
            "failed": "failed",
            "queued": "queued",
        }.get(run_status, "pending")
        return {"time": hhmm(row), "project": label, "name": row.get("name") or label, "status": status}

    render_items = [render_row(row) for row in renders]
    upload_items = [upload_row(row) for row in uploads]

    next_render = next(
        (item for item in render_items if item["status"] in ("not started", "queued", "rendering")),
        None,
    )
    next_upload = next(
        (item for item in upload_items if item["status"] in ("pending", "queued", "running")),
        None,
    )

    done = sum(1 for item in render_items if item["status"] == "done")
    failed = sum(1 for item in render_items if item["status"] == "failed")

    return {
        "date": day.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "renders": render_items,
        "uploads": upload_items,
        "summary": {
            "renders_done": done,
            "renders_total": len(render_items),
            "renders_failed": failed,
            "uploads_done": sum(1 for item in upload_items if item["status"] == "done"),
            "uploads_total": len(upload_items),
            "next_render": next_render,
            "next_upload": next_upload,
        },
    }


def when(item: dict, now: str) -> str:
    return item["time"] + (" (due)" if item["time"] < now else "")


def print_report(report: dict, short: bool) -> None:
    now = datetime.now().strftime("%H:%M")
    same_day = report["date"] == datetime.now().date().isoformat()
    label = "TODAY" if same_day else "STATUS"
    print(f"{label} {report['date']}  now {now} (Asia/Kolkata)")
    summary = report["summary"]

    if short:
        if summary["next_render"]:
            item = summary["next_render"]
            print(f"Next video: {item['project']} at {when(item, now)}")
        else:
            print("Next video: none left" + (" today" if same_day else " on that date"))
        pending = [item for item in report["uploads"] if item["status"] != "done"]
        if pending:
            print("Uploads left: " + ", ".join(f"{item['project']} {when(item, now)}" for item in pending))
        else:
            print("Uploads: all done")
        print(
            f"Renders done: {summary['renders_done']}/{summary['renders_total']}"
            + (f", failed: {summary['renders_failed']}" if summary["renders_failed"] else "")
        )
        return

    print()
    print("RENDER SCHEDULE")
    if not report["renders"]:
        print("  (none)")
    for item in report["renders"]:
        print(f"  {item['time']}  {item['project']:<14} {item['status']}")

    print()
    print("UPLOAD / PUBLISH")
    if not report["uploads"]:
        print("  (none)")
    for item in report["uploads"]:
        print(f"  {item['time']}  {item['project']:<22} {item['status']}")

    print()
    print(
        f"SUMMARY renders {summary['renders_done']}/{summary['renders_total']}"
        + (f" ({summary['renders_failed']} failed)" if summary["renders_failed"] else "")
        + f" | uploads {summary['uploads_done']}/{summary['uploads_total']}"
    )
    if summary["next_render"]:
        item = summary["next_render"]
        print(f"NEXT render: {item['project']} at {when(item, now)}")
    else:
        print("NEXT render: none left")
    if summary["next_upload"]:
        item = summary["next_upload"]
        print(f"NEXT upload: {item['project']} at {when(item, now)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Today's render and upload status (ASCII only)")
    parser.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    parser.add_argument("--short", action="store_true", help="Only the one-line answer")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    try:
        day = parse_date(args.date)
    except ValueError:
        print("ERROR: --date must be YYYY-MM-DD", file=sys.stderr)
        return 2

    report = build_report(day)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args.short)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
