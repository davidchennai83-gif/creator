"""Growth-agent guard tests.

These drive the real code against a synthetic storage root (so nothing touches
the live scheduler, jobs database or social accounts) and prove the important
safety property: the recovery path must never create a *second* completed video
for the same show/day — the uploader would post both.

Run:  python growth_test.py
"""
import json
import shutil
import sqlite3
import sys
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")


TMP = (BACKEND / "storage" / "_growthtest").resolve()
if TMP.exists():
    shutil.rmtree(TMP)
(TMP / "video_creator").mkdir(parents=True)
(TMP / "automation" / "projects").mkdir(parents=True)

from app.config import settings  # noqa: E402

settings.STORAGE_PATH = str(TMP)
settings.AUTOMATION_PATH = str(TMP / "automation")

from app.video_creator import jobs  # noqa: E402
from app.growth import agent as growth  # noqa: E402
from app.growth import playbook  # noqa: E402

OWNER = "11111111-1111-1111-1111-111111111111"
IST = timedelta(hours=5, minutes=30)

# ---------------------------------------------------------------- fixtures
def write_schedules(tasks):
    with sqlite3.connect(TMP / "video_creator" / "schedules.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)")
        db.execute("DELETE FROM schedules")
        for t in tasks:
            db.execute("INSERT OR REPLACE INTO schedules VALUES (?,?,?)", (t["id"], t["owner"], json.dumps(t)))


def write_jobs(items):
    with sqlite3.connect(TMP / "video_creator" / "jobs.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)")
        db.execute("DELETE FROM jobs")
        for j in items:
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?)", (j["id"], j["owner"], json.dumps(j)))


def task(project, run_time, **kw):
    base = {"id": f"t-{project}", "owner": OWNER, "project": project, "run_time": run_time,
            "frequency": "daily", "start_date": "2020-01-01", "end_date": "2036-09-01",
            "voice": "ta-IN-PallaviNeural", "enabled": True, "platforms": []}
    base.update(kw)
    return base


def job(kind, day, status, jid=None):
    return {"id": jid or f"j-{kind}-{status}", "owner": OWNER, "date": day, "kind": kind,
            "status": status, "points": []}


TODAY = growth.today()

print("growth agent tests")
print("  synthetic root:", TMP)

# ------------------------------------------------- 1. frequency helper
check("_runs_today daily", growth._runs_today(task("history", "08:00"), growth.now_ist()))
check("_runs_today outside range",
      not growth._runs_today(task("history", "08:00", start_date="2030-01-01"), growth.now_ist()))
wd = growth.now_ist().weekday()
check("_runs_today weekly match",
      growth._runs_today(task("gk", "08:00", frequency="weekly", weekdays=[wd]), growth.now_ist()))
check("_runs_today weekly miss",
      not growth._runs_today(task("gk", "08:00", frequency="weekly", weekdays=[(wd + 1) % 7]), growth.now_ist()))
check("_runs_today custom interval 1",
      growth._runs_today(task("gk", "08:00", frequency="custom", interval_days=1), growth.now_ist()))
check("_runs_today monthly day",
      growth._runs_today(task("gk", "08:00", frequency="monthly",
                              month_day=growth.now_ist().day), growth.now_ist()))
check("_runs_today monthly other day",
      not growth._runs_today(task("gk", "08:00", frequency="monthly",
                                  month_day=(growth.now_ist().day % 28) + 1), growth.now_ist()))

# ------------------------------------------------- 2. UTC -> IST run day
utc_late = datetime(2026, 10, 14, 19, 30, tzinfo=timezone.utc)  # 01:00 IST on the 15th
check("_run_day rolls over to IST", growth._run_day({"started_at": utc_late.isoformat()}) == "2026-10-15",
      growth._run_day({"started_at": utc_late.isoformat()}))
utc_early = datetime(2026, 10, 14, 3, 0, tzinfo=timezone.utc)   # 08:30 IST on the 14th
check("_run_day same IST day", growth._run_day({"started_at": utc_early.isoformat()}) == "2026-10-14")
check("_run_day junk is empty", growth._run_day({"started_at": "not-a-date"}) == "")

# ------------------------------------------------- 3. snapshot / missed
write_schedules([task("history", "00:05"), task("gk", "00:06")])
write_jobs([job("history", TODAY, "complete")])
snap = growth.snapshot(TODAY)
check("snapshot sees expected renders", snap["expected_renders"] == ["gk", "history"], str(snap["expected_renders"]))
check("snapshot sees rendered", snap["rendered"] == ["history"], str(snap["rendered"]))
check("snapshot finds the missed render", snap["missed_renders"] == ["gk"], str(snap["missed_renders"]))

# ------------------------------------------------- 4. recovery re-queues
calls = []
real_new = jobs.new


def fake_new(owner, day, voice, kind, auto_render=False, job_id=None, **kw):
    calls.append({"owner": owner, "day": day, "voice": voice, "kind": kind, "job_id": job_id})
    j = job(kind, day.isoformat(), "new", jid=job_id)
    jobs.save(j)
    return j


jobs.new = fake_new
try:
    from uuid import NAMESPACE_URL, uuid5
    expected_gk_id = uuid5(NAMESPACE_URL, f"growth:gk:{TODAY}")
    budget = {"recoveries": 0, "uploads": 0}
    actions = growth._recover_renders(snap, {"recover_renders": True}, budget)
    check("recovery queued exactly the missed kind", len(actions) == 1 and actions[0]["kind"] == "gk", str(actions))
    check("recovery did not touch the rendered kind",
          all(c["kind"] != "history" for c in calls), str(calls))
    check("recovery used a deterministic id",
          bool(actions) and str(actions[0]["job_id"]) == str(expected_gk_id),
          f'{actions[0]["job_id"] if actions else None} vs {expected_gk_id}')
    check("recovery consumed budget", budget["recoveries"] == 1)

    # in-flight job for the same kind must block a second queue
    calls.clear()
    write_jobs([job("history", TODAY, "complete"), job("gk", TODAY, "rendering")])
    snap2 = growth.snapshot(TODAY)
    budget = {"recoveries": 0, "uploads": 0}
    growth._recover_renders(snap2, {"recover_renders": True}, budget)
    check("in-progress render is not duplicated", not calls, str(calls))

    # a completed video must never be re-queued
    calls.clear()
    write_jobs([job("history", TODAY, "complete"), job("gk", TODAY, "complete")])
    snap3 = growth.snapshot(TODAY)
    check("nothing missed once all complete", snap3["missed_renders"] == [], str(snap3["missed_renders"]))
    budget = {"recoveries": 0, "uploads": 0}
    growth._recover_renders(snap3, {"recover_renders": True}, budget)
    check("complete slate queues nothing", not calls, str(calls))

    # disabled switch is honoured
    calls.clear()
    write_jobs([job("history", TODAY, "complete")])
    budget = {"recoveries": 0, "uploads": 0}
    growth._recover_renders(growth.snapshot(TODAY), {"recover_renders": False}, budget)
    check("recover_renders=False does nothing", not calls)

    # per-day limit
    calls.clear()
    for i in range(6):
        write_schedules([task(f"k{i}", "00:05")])
    write_jobs([])
    budget = {"recoveries": growth.LIMITS["max_recoveries_per_day"], "uploads": 0}
    growth._recover_renders(growth.snapshot(TODAY), {"recover_renders": True}, budget)
    check("daily recovery limit respected", not calls,
          f"limit={growth.LIMITS['max_recoveries_per_day']} calls={len(calls)}")
finally:
    jobs.new = real_new

# ------------------------------------------------- 5. uploads are gated
write_schedules([task("history", "00:05"), task("automation:YouTube Upload", "00:10")])
write_jobs([job("history", TODAY, "complete")])
snap4 = growth.snapshot(TODAY)
check("snapshot knows the expected upload", snap4["expected_uploads"] == ["YouTube Upload"],
      str(snap4["expected_uploads"]))
check("snapshot sees no upload yet", snap4["missed_uploads"] == ["history"], str(snap4["missed_uploads"]))

# upload retry must not fire while renders are still missing
write_jobs([])
snap5 = growth.snapshot(TODAY)
runs = []


class FakeRunner:
    gate = type("G", (), {"locked": staticmethod(lambda: False)})()

    @staticmethod
    def listing(owner, limit=30):
        return []

    @staticmethod
    def run(owner, project, file="main.py"):
        runs.append(project)
        return {"id": "run-1"}

    @staticmethod
    def root():
        return TMP / "automation"


import app.automation.runner as real_runner  # noqa: E402
import app.automation as automation_pkg  # noqa: E402
saved_runner = real_runner
sys.modules["app.automation.runner"] = FakeRunner
automation_pkg.runner = FakeRunner
try:
    budget = {"recoveries": 0, "uploads": 0}
    growth._recover_uploads(snap5, {"recover_uploads": True}, budget)
    check("no upload retry while renders are missing", not runs, str(runs))

    budget = {"recoveries": 0, "uploads": 0}
    growth._recover_uploads(snap4, {"recover_uploads": True}, budget)
    check("upload retried once the slate is ready", runs == ["YouTube Upload"], str(runs))
    check("upload retry consumed budget", budget["uploads"] == 1)

    # A run that *reported success* and still left today's video unposted MUST be
    # retried: that is the exact real gap this agent exists to close (a run can
    # exit 0 having posted only the previous day's videos). The uploader itself
    # skips anything already in its log, so retrying cannot duplicate a post.
    runs.clear()

    class FakeDone(FakeRunner):
        @staticmethod
        def listing(owner, limit=30):
            return [{"status": "completed", "exit_code": 0,
                     "started_at": datetime.now(timezone.utc).isoformat()}]

    sys.modules["app.automation.runner"] = FakeDone
    automation_pkg.runner = FakeDone
    budget = {"recoveries": 0, "uploads": 0}
    growth._recover_uploads(snap4, {"recover_uploads": True}, budget)
    check("a run that left today's video unposted is retried", runs == ["YouTube Upload"], str(runs))
finally:
    sys.modules["app.automation.runner"] = saved_runner
    automation_pkg.runner = saved_runner

# ------------------------------------------------- 5b. uploaded-log parsing
upload_proj = TMP / "automation" / "projects" / "YouTube Upload"
upload_proj.mkdir(parents=True, exist_ok=True)
posted = TMP / "video_creator" / "job-posted" / "history.mp4"
posted.parent.mkdir(parents=True, exist_ok=True)
posted.write_bytes(b"x")
other_day = TMP / "video_creator" / "job-old" / "history.mp4"
other_day.parent.mkdir(parents=True, exist_ok=True)
other_day.write_bytes(b"x")
(upload_proj / "uploaded.log").write_text(f"{posted}\n{other_day}\n", encoding="utf-8")
write_jobs([job("gk", TODAY, "complete", jid="job-posted"),
            job("history", "2026-01-01", "complete", jid="job-old")])
detected = growth._uploaded_kinds(TODAY)
check("uploaded log maps job id -> kind", detected == {"gk"}, str(detected))
check("uploaded log ignores other days", "history" not in detected, str(detected))

# per-platform view: every finished video is logged, so nothing is missing
snap6 = growth.snapshot(TODAY)
check("fully posted platform needs no retry", snap6["missed_uploads"] == [], str(snap6["missed_uploads"]))
check("no per-platform gaps when all logged", snap6["missed_uploads_by_platform"] == {},
      str(snap6["missed_uploads_by_platform"]))

# remove the log again -> the gap must surface for that platform by name
(upload_proj / "uploaded.log").unlink()
snap7 = growth.snapshot(TODAY)
check("per-platform gap is reported by name",
      snap7["missed_uploads_by_platform"] == {"YouTube Upload": ["gk"]},
      str(snap7["missed_uploads_by_platform"]))
check("union still reports the kind", snap7["missed_uploads"] == ["gk"], str(snap7["missed_uploads"]))
(upload_proj / "uploaded.log").write_text(f"{posted}\n{other_day}\n", encoding="utf-8")

# ------------------------------------------------- 6. tick / report / status
write_schedules([task("history", "00:05")])
write_jobs([job("history", TODAY, "complete")])
growth.save_config({"enabled": True, "recover_renders": True, "recover_uploads": True})
out = growth.tick()
check("tick records a snapshot", (out.get("snapshot") or {}).get("day") == TODAY)
check("tick records KPIs", (out.get("kpis") or {}).get("rendered_today") == 1, str(out.get("kpis")))
check("streak counts today", growth.streak(growth.load_state()) >= 1)
state = growth.load_state()
check("variant rotation stored", (state.get("variant") or {}).get("history", {}).get("hook"))

growth.save_config({"enabled": False})
check("disabled agent skips", growth.tick().get("skipped") == "disabled")
growth.save_config({"enabled": True})

rep = growth.write_report()
check("report written with the day", rep["day"] == TODAY and (growth._reports_dir() / f"{TODAY}.json").is_file())
check("report states the scope", "No bots" in rep["note"])
st = growth.status()
check("status exposes kpis + scope", "kpis" in st and "No bots" in st["scope"])

# ------------------------------------------------- 7. playbook determinism
v1 = playbook.variant_for("history", "2026-10-14")
v2 = playbook.variant_for("history", "2026-10-14")
v3 = playbook.variant_for("history", "2026-10-15")
check("variant is deterministic", v1 == v2)
check("variant changes across days", v1 != v3, f"{v1['hook']} / {v1['cta']} vs {v3['hook']} / {v3['cta']}")
check("every kind has a hook", all(playbook.variant_for(k, "2026-10-14")["hook"] for k in playbook.HOOKS))

# ------------------------------------------------- result
failed = [r for r in RESULTS if not r[1]]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
if failed:
    print("FAILURES:")
    for name, _ok, detail in failed:
        print(f"  - {name} {detail}")
shutil.rmtree(TMP, ignore_errors=True)
print("ALL OK" if not failed else "TESTS FAILED")
sys.exit(1 if failed else 0)
