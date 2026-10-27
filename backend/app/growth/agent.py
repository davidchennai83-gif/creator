"""24x7 subscriber-growth agent.

WHAT THIS IS — AND WHAT IT DELIBERATELY IS NOT
---------------------------------------------
Buying followers, view/sub bots, engagement pods and auto-following other
accounts all violate the platform terms and get a channel banned or shadowed.
This agent does none of that. It works only the levers that genuinely grow a
small daily channel, all local and free:

1. **Delivery guarantee (the big one).** For a daily channel the single largest
   growth factor is *never missing a day*. The video scheduler already queues
   each day's renders — but as soon as it has queued one it advances `next_run`
   to tomorrow, so a job that **fails** is never retried and a slot silently
   produces nothing. Same for upload runs. This agent watches for exactly that
   gap and re-queues it: a scheduled show with no completed render, or a social
   upload run that errored, gets another attempt the same day.
2. **Publishing streak + coverage.** Real, measurable growth KPIs (consecutive
   days with a complete slate, per-kind coverage, uploads per day) recorded to
   `storage/growth/` so progress is visible instead of guessed.
3. **Fresh appeals.** A daily-rotating hook / CTA / hashtag pack per show
   (`app/growth/playbook.py`) so the channel keeps varying how it asks for a
   subscribe.

Every action is bounded (see the `LIMITS` below), recorded in an event log and
reversible. The agent never touches credentials, never auto-likes, never
auto-comments and never follows anyone.
"""
import json
import logging
import threading
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.config.settings import settings
from . import playbook

log = logging.getLogger(__name__)

_LOCK = threading.RLock()
_LAST_TICK = {"at": 0.0}
BOOT = time.time()

LIMITS = {
    # Only act once a slot is well past, so we never race the normal scheduler.
    "grace_minutes": 45,
    # Upper bound on automatic re-queues in one IST day.
    "max_recoveries_per_day": 4,
    # Upper bound on automatic upload retries in one IST day.
    "max_upload_retries_per_day": 3,
    # Don't even look at the recovery path more often than this.
    "min_seconds_between_actions": 300,
}

IST = timedelta(hours=5, minutes=30)

DEFAULT_CONFIG = {
    "enabled": True,
    "recover_renders": True,
    "recover_uploads": True,
    "record_kpis": True,
}


def root() -> Path:
    path = Path(settings.STORAGE_PATH) / "growth"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return root() / "state.json"


def _events_path() -> Path:
    return root() / "events.jsonl"


def _reports_dir() -> Path:
    path = root() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_ist() -> datetime:
    """Naive IST wall clock — the scheduler stores its times the same way."""
    return datetime.utcnow() + IST


def today() -> str:
    return now_ist().date().isoformat()


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        registry = root() / "config.json"
        if registry.is_file():
            cfg.update(json.loads(registry.read_text(encoding="utf-8")))
    except Exception as exc:
        log.warning("growth config unreadable: %s", exc)
    return cfg


def save_config(patch: dict) -> dict:
    cfg = load_config()
    cfg.update({k: v for k, v in patch.items() if k in DEFAULT_CONFIG and v is not None})
    (root() / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def load_state() -> dict:
    try:
        if _state_path().is_file():
            return json.loads(_state_path().read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("growth state unreadable: %s", exc)
    return {}


def save_state(state: dict) -> None:
    try:
        _state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("growth state unwritable: %s", exc)


def record(event: str, text: str, **extra) -> dict:
    """Append to the growth event log (also mirrored into state['events'])."""
    item = {"at": now_ist().isoformat(timespec="seconds"), "event": event, "text": text}
    item.update(extra)
    try:
        with _events_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.warning("growth event unwritable: %s", exc)
    with _LOCK:
        state = load_state()
        events = state.get("events") or []
        events.append(item)
        state["events"] = events[-60:]
        save_state(state)
    return item


# --------------------------------------------------------------------------
# What is supposed to happen today, and what actually happened.
# --------------------------------------------------------------------------
def _schedule_rows():
    """Every configured schedule (video projects and automation projects)."""
    import sqlite3
    from app.video_creator import jobs
    db_path = jobs.root() / "schedules.sqlite3"
    if not db_path.is_file():
        return []
    rows = []
    try:
        with sqlite3.connect(db_path, timeout=30) as db:
            for (body,) in db.execute("SELECT body FROM schedules").fetchall():
                try:
                    rows.append(json.loads(body))
                except Exception:
                    continue
    except Exception as exc:
        log.warning("growth could not read schedules: %s", exc)
    return rows


def _runs_today(task, moment: datetime) -> bool:
    """Mirror of schedules.next_run's frequency test, for 'is today a run day'."""
    try:
        start = date.fromisoformat(task["start_date"])
        end = date.fromisoformat(task["end_date"])
    except Exception:
        return False
    day = moment.date()
    if not (start <= day <= end):
        return False
    freq = task.get("frequency")
    if freq == "daily":
        return True
    if freq == "weekly":
        return day.weekday() in (task.get("weekdays") or [])
    if freq == "monthly":
        import calendar
        last = calendar.monthrange(day.year, day.month)[1]
        return day.day == min(int(task.get("month_day") or 1), last)
    if freq == "custom":
        interval = max(1, int(task.get("interval_days") or 1))
        return (day - start).days % interval == 0
    return False


def _due_today(moment: datetime) -> list:
    """Tasks that should already have started by `moment` (IST), today."""
    due = []
    for task in _schedule_rows():
        if not task.get("enabled") or not task.get("run_time"):
            continue
        if not _runs_today(task, moment):
            continue
        try:
            hour, minute = (int(x) for x in str(task["run_time"]).split(":"))
        except Exception:
            continue
        start = datetime.combine(moment.date(), dtime(hour, minute))
        grace = timedelta(minutes=LIMITS["grace_minutes"])
        if moment >= start + grace:
            due.append({"task": task, "start": start, "run_time": task["run_time"]})
    return due


def _all_jobs() -> dict:
    """id -> job body, for every video job on disk."""
    import sqlite3
    from app.video_creator import jobs
    db_path = jobs.root() / "jobs.sqlite3"
    if not db_path.is_file():
        return {}
    out = {}
    try:
        with sqlite3.connect(db_path, timeout=30) as db:
            for (body,) in db.execute("SELECT body FROM jobs").fetchall():
                try:
                    job = json.loads(body)
                except Exception:
                    continue
                if job.get("id"):
                    out[job["id"]] = job
    except Exception as exc:
        log.warning("growth could not read jobs: %s", exc)
    return out


def _jobs_today(day: str) -> list:
    return [j for j in _all_jobs().values() if j.get("date") == day]


# Uploader project -> the skip log it appends to. The names differ (YouTube uses
# a plain "uploaded.log"), which previously made YouTube invisible to this check.
PLATFORM_LOGS = {
    "YouTube Upload": "uploaded.log",
    "Facebook Upload": "fb_uploaded.log",
    "Instagram Upload": "ig_uploaded.log",
}


def _uploaded_by_platform(day: str) -> dict:
    """{platform: {kinds already posted there for `day`}}.

    Each uploader keeps an append-only log of the *video files* it has posted —
    one absolute `.../video_creator/<job_id>/history.mp4` path per line — so the
    job id (and through it the show and its date) tells us what went out. Gaps
    are tracked per platform because a successful run for one is no guarantee
    for another.
    """
    from app.automation import runner
    base = runner.root() / "projects"
    jobs = _all_jobs()
    result = {}
    for platform, log_name in PLATFORM_LOGS.items():
        kinds = set()
        log_file = base / platform / log_name
        if log_file.is_file():
            try:
                # Today's entries are appended last; keep the read bounded.
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-800:]
            except OSError:
                lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                job = jobs.get(Path(line).parent.name)
                if job and job.get("date") == day and job.get("kind"):
                    kinds.add(job["kind"])
        result[platform] = kinds
    return result


def _uploaded_kinds(day: str) -> set:
    """Union of everything posted for `day` on any platform."""
    merged = set()
    for kinds in _uploaded_by_platform(day).values():
        merged |= kinds
    return merged


def _run_day(run: dict) -> str:
    """IST calendar day of an automation run (started_at is stored in UTC)."""
    raw = str(run.get("started_at") or "")
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc) + IST).date().isoformat()


def snapshot(day: str | None = None) -> dict:
    """Today's growth picture: what was expected, rendered, uploaded."""
    day = day or today()
    moment = now_ist()
    due = _due_today(moment)
    expected = sorted({t["task"]["project"].split(":", 1)[-1]
                       for t in due if not t["task"]["project"].startswith("automation:")})
    expected_uploads = sorted({t["task"]["project"].split(":", 1)[-1]
                               for t in due if t["task"]["project"].startswith("automation:")})
    jobs = _jobs_today(day)
    complete = sorted({j["kind"] for j in jobs if j.get("status") == "complete"})
    failed = sorted({j["kind"] for j in jobs if j.get("status") == "failed"})
    in_progress = sorted({j["kind"] for j in jobs
                          if j.get("status") in ("new", "writing", "rendering")})
    uploaded = sorted(_uploaded_kinds(day))
    by_platform = _uploaded_by_platform(day)
    # Only shows that actually have a finished video today can be uploaded, and
    # only platforms that are actually scheduled today are tracked — otherwise
    # unscheduled platforms would show as permanent gaps.
    postable = set(complete)
    missing_by_platform = {p: sorted(postable - by_platform.get(p, set()))
                           for p in expected_uploads}
    return {
        "day": day,
        "at": moment.isoformat(timespec="seconds"),
        "expected_renders": expected,
        "expected_uploads": expected_uploads,
        "rendered": complete,
        "failed": failed,
        "in_progress": in_progress,
        "uploaded": uploaded,
        "uploaded_by_platform": {p: sorted(k) for p, k in by_platform.items()},
        "missed_renders": [k for k in expected if k not in complete],
        # A show is only "delivered" when every scheduled platform has it.
        "missed_uploads": sorted({k for v in missing_by_platform.values() for k in v}),
        "missed_uploads_by_platform": {p: v for p, v in missing_by_platform.items() if v},
    }


def streak(state: dict = None) -> int:
    """Consecutive IST days with at least one completed render (today counts)."""
    state = state or load_state()
    known = set(state.get("complete_days") or [])
    snap = state.get("snapshot") or {}
    if snap.get("day") == today() and snap.get("rendered"):
        known.add(snap["day"])
    if not known:
        return 0
    count = 0
    cursor = now_ist().date()
    if cursor.isoformat() not in known:
        cursor -= timedelta(days=1)
    while cursor.isoformat() in known:
        count += 1
        cursor -= timedelta(days=1)
    return count


# --------------------------------------------------------------------------
# The two recovery actions.
# --------------------------------------------------------------------------
def _recover_renders(snap: dict, cfg: dict, budget: dict) -> list:
    """Re-queue a scheduled show that produced no completed video today."""
    from app.video_creator import jobs
    actions = []
    if not cfg.get("recover_renders"):
        return actions
    for kind in snap["missed_renders"]:
        if budget["recoveries"] >= LIMITS["max_recoveries_per_day"]:
            record("limit", f"Render recovery limit reached for {snap['day']}")
            break
        # Never queue a second video for a show that already produced one today,
        # and never race a job that is still writing/rendering — the uploader
        # posts every completed video for the day, so a duplicate would double-post.
        if kind in snap["rendered"] or kind in snap["in_progress"]:
            continue
        if jobs.gate.locked():
            record("wait", f"{kind}: a render is already running; will retry")
            break
        job_id = str(uuid5(NAMESPACE_URL, f"growth:{kind}:{snap['day']}"))
        task = next((t["task"] for t in _due_today(now_ist())
                     if t["task"]["project"].split(":", 1)[-1] == kind
                     and not t["task"]["project"].startswith("automation:")), None)
        if not task:
            continue
        try:
            job = jobs.new(task["owner"], now_ist().date(), task.get("voice") or "ta-IN-PallaviNeural",
                           kind, auto_render=True, job_id=job_id)
        except ValueError as exc:
            # gate busy / unknown template — harmless, retry next tick
            record("wait", f"{kind}: {exc}")
            break
        except Exception as exc:
            record("error", f"{kind}: re-queue failed: {exc}")
            continue
        budget["recoveries"] += 1
        actions.append({"kind": kind, "job_id": job["id"]})
        record("recover_render", f"Re-queued missing render for {kind}", kind=kind, job_id=job["id"])
    return actions


def _recover_uploads(snap: dict, cfg: dict, budget: dict) -> list:
    """Re-run a social upload whose platform is still missing today's videos.

    A run can report success and still leave gaps (the real failure earlier today
    posted yesterday's videos and returned exit 0), so the decision is based on
    what is actually *logged*, not on whether a run happened. Re-running is safe:
    each uploader skips anything already in its own log, so it can only add the
    missing videos.
    """
    from app.automation import runner
    actions = []
    if not cfg.get("recover_uploads"):
        return actions
    missing = snap.get("missed_uploads_by_platform") or {}
    if not missing:
        return actions
    if not snap["expected_renders"] or snap["missed_renders"]:
        # Nothing to upload yet, or the slate is still rendering.
        return actions
    if runner.gate.locked():
        record("wait", "An automation run is already active; upload retry deferred")
        return actions
    for platform in snap["expected_uploads"]:
        if not missing.get(platform):
            continue
        if budget["uploads"] >= LIMITS["max_upload_retries_per_day"]:
            record("limit", f"Upload retry limit reached for {snap['day']}")
            break
        owner = _owner_for(platform)
        if not owner:
            continue
        runs = runner.listing(owner, limit=20)
        today_runs = [r for r in runs if _run_day(r) == snap["day"]]
        if any(r.get("status") == "running" for r in today_runs):
            continue
        try:
            run = runner.run(owner, platform, "main.py")
        except Exception as exc:
            record("error", f"{platform}: upload retry failed: {exc}")
            continue
        budget["uploads"] += 1
        actions.append({"project": platform, "run_id": run["id"],
                        "missing": missing[platform]})
        record("recover_upload",
               f"Re-ran {platform} for {len(missing[platform])} missing video(s)",
               project=platform, run_id=run["id"], missing=missing[platform])
    return actions


def _owner_for(project: str):
    for task in _schedule_rows():
        if task.get("project", "").split(":", 1)[-1] == project:
            return task.get("owner")
    return None


# --------------------------------------------------------------------------
# Tick / report / status
# --------------------------------------------------------------------------
def tick() -> dict:
    """One growth pass. Cheap, idempotent, safe to call every minute."""
    cfg = load_config()
    if not cfg.get("enabled"):
        return {"skipped": "disabled"}

    monotonic = time.monotonic()
    with _LOCK:
        state = load_state()
        last_action = float(state.get("last_action_monotonic") or 0.0)
        day = today()
        if state.get("day") != day:
            state["day"] = day
            state["recoveries_today"] = 0
            state["uploads_today"] = 0
            # a brand-new day: roll the accumulated KPIs
            snap_prev = state.get("snapshot") or {}
            if snap_prev.get("day") and snap_prev.get("rendered"):
                days = set(state.get("complete_days") or [])
                days.add(snap_prev["day"])
                state["complete_days"] = sorted(days)[-400:]
            state["variant"] = {k: playbook.variant_for(k, day)
                                for k in ("history", "indian-law", "make-money", "thirukkural",
                                          "english", "gk", "kids", "health", "motivation", "news")}
            save_state(state)
        budget = {"recoveries": int(state.get("recoveries_today") or 0),
                  "uploads": int(state.get("uploads_today") or 0)}

    snap = snapshot(day)
    actions = {"renders": [], "uploads": []}

    if cfg.get("recover_renders") or cfg.get("recover_uploads"):
        if monotonic - last_action >= LIMITS["min_seconds_between_actions"]:
            actions["renders"] = _recover_renders(snap, cfg, budget)
            snap_after = snapshot(day)
            actions["uploads"] = _recover_uploads(snap_after, cfg, budget)
            if actions["renders"] or actions["uploads"]:
                monotonic_stamp = time.monotonic()
            else:
                monotonic_stamp = last_action
        else:
            monotonic_stamp = last_action
    else:
        monotonic_stamp = last_action

    # Refresh the snapshot after any action so the KPIs are accurate.
    snap = snapshot(day)

    with _LOCK:
        state = load_state()
        state.update({
            "day": day,
            "last_tick": now_ist().isoformat(timespec="seconds"),
            "snapshot": snap,
            "recoveries_today": budget["recoveries"],
            "uploads_today": budget["uploads"],
            "last_action_monotonic": monotonic_stamp,
        })
        state["streak"] = streak(state)
        state["kpis"] = {
            "streak_days": state["streak"],
            "rendered_today": len(snap["rendered"]),
            "expected_today": len(snap["expected_renders"]),
            "uploads_today": len(snap["uploaded"]),
            "missed_renders": snap["missed_renders"],
            "missed_uploads": snap["missed_uploads"],
        }
        save_state(state)
    _LAST_TICK["at"] = time.time()
    return {"snapshot": snap, "kpis": state["kpis"], "actions": actions}


def write_report(day: str | None = None) -> dict:
    """Persist the daily growth report (called by the daily ops cycle too)."""
    day = day or today()
    state = load_state()
    snap = snapshot(day)
    report = {
        "day": day,
        "generated_at": now_ist().isoformat(timespec="seconds"),
        "streak_days": streak(state),
        "rendered": snap["rendered"],
        "expected_renders": snap["expected_renders"],
        "missed_renders": snap["missed_renders"],
        "uploaded": snap["uploaded"],
        "expected_uploads": snap["expected_uploads"],
        "missed_uploads": snap["missed_uploads"],
        "recoveries_today": state.get("recoveries_today", 0),
        "upload_retries_today": state.get("uploads_today", 0),
        "variant": (state.get("variant") or {}).get("history"),
        "note": "Legitimate growth only: publishing consistency, coverage and fresh "
                "appeals. No bots, no fake engagement.",
    }
    (_reports_dir() / f"{day}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def report(day: str | None = None) -> dict:
    day = day or today()
    path = _reports_dir() / f"{day}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return write_report(day)


def speak_line() -> str:
    """One short Tamil line for the voice heartbeat."""
    state = load_state()
    kpis = state.get("kpis") or {}
    if not kpis:
        return ""
    missing = len(kpis.get("missed_renders") or [])
    if missing:
        return f"இன்று {missing} வீடியோ மிஸ் ஆகியிருக்கு, agent திரும்ப முயற்சி செய்யுது."
    return (f"வளர்ச்சி: {kpis.get('rendered_today', 0)} வீடியோ ரெடி, "
            f"{kpis.get('uploads_today', 0)} upload, {kpis.get('streak_days', 0)} நாள் தொடர்ச்சி.")


def status() -> dict:
    state = load_state()
    return {
        "config": load_config(),
        "kpis": state.get("kpis") or {},
        "snapshot": state.get("snapshot") or snapshot(),
        "streak_days": streak(state),
        "variant": state.get("variant") or {},
        "report": report(),
        "events": (state.get("events") or [])[-20:],
        "limits": LIMITS,
        "scope": "Legitimate growth only — publishing consistency, coverage and fresh "
                 "appeals. No bots and no fake engagement.",
    }
