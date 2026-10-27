"""Autonomous daily operations: self-maintenance + self-improvement.

This module is the engine behind "the platform upgrades itself every day".
It runs inside the always-on backend (driven by the voice-agent loop) so it
needs no human, no prompt and no permission. Once per IST day it:

1. backs up every SQLite database (consistent snapshot, 7-day rotation),
2. writes a daily health + earnings report,
3. prunes old backups / reports / voice samples,
4. and launches an *unattended* OpenCode session that ships exactly one safe
   improvement taken from the roadmap in ``UPGRADES.md``.

Every step is best-effort and individually guarded: a failure here can never
take the live site down. State lives under ``storage/ops``.
"""
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config.settings import settings

log = logging.getLogger(__name__)

IST = timezone(timedelta(minutes=330))
_LOCK = threading.RLock()
_BUSY = threading.Event()
_BACKUP_KEEP = 7
_REPORT_KEEP = 45
_SAMPLE_KEEP_DAYS = 14

PROJECT = Path(settings.STORAGE_PATH).resolve().parent.parent
ROADMAP = PROJECT / "UPGRADES.md"


def _opencode_cli() -> Path:
    """Find OpenCode without assuming the original developer's home folder.

    On Windows the npm shim has no extension; CreateProcess cannot run it
    directly. Prefer a real .exe so the detached nightly job can start.
    """
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    if local:
        desktop_cli = Path(local) / "Programs" / "@opencodedesktop" / "resources" / "opencode-cli.exe"
        if desktop_cli.is_file():
            return desktop_cli
    if appdata:
        npm_cli = Path(appdata) / "npm" / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
        if npm_cli.is_file():
            return npm_cli
    home_cli = Path.home() / "AppData" / "Local" / "Programs" / "@opencodedesktop" / "resources" / "opencode-cli.exe"
    if home_cli.is_file():
        return home_cli
    for name in ("opencode.exe", "opencode.cmd", "opencode"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return Path("opencode")


CLI = _opencode_cli()
MODEL = os.environ.get("OPENCODE_DAILY_MODEL", "ollama/qwen2.5-coder:7b")

DEFAULT_CONFIG = {
    "ai_upgrade_enabled": True,
    "backup_enabled": True,
    "daily_report_enabled": True,
    "voice_check_enabled": True,
}

AI_PROMPT = """You are the autonomous daily maintainer of the CreatorMart creator platform at {project}.
This is an UNATTENDED scheduled run: there is NO human to answer questions, so never ask anything — inspect, decide, act, test, and stop.

Read these two files first:
- {project}/UPGRADES.md  (the roadmap: Mission, Rules, "Next" list, "Done" log)
- {project}/backend/storage/ops/reports/{day}.json  (today's health + earnings report)

How the platform runs:
- Backend: FastAPI in backend/, started with the project interpreter
  {python} backend/start.py (no auto-reload; Python changes take effect only after a restart).
- Frontend: React in frontend/, served from dist/ after `npm.cmd run build`.
- Data: SQLite under backend/storage/. Never delete or corrupt user data.
- Tests: backend files like *_test.py / *_e2e.py, plus helpers in {temp}.

Hard rules (never break the live site):
1. Ship at most ONE small, safe, additive improvement. Prefer the top unchecked item in UPGRADES.md "Next"; if the list is empty, add a genuinely useful, low-risk one.
2. If today's report is unhealthy (ok=false, narration_ok=false, silent videos, disk <15GB), FIX THAT FIRST instead of adding a feature.
3. Never invent credentials (no Facebook/Instagram passwords, no UPI id, no API keys). Never auto-post to social media. Never print secrets.
4. Run `python -m py_compile` on every Python file you change, and the matching test script(s); run `npm.cmd run build` if you touched frontend. If any check fails, REVERT your change and stop.
5. Do not change how the backend is started, do not edit the watchdog, do not restart services. Frontend builds are safe (served live). If you changed backend Python and every check passed, create the empty file backend/storage/ops/restart.requested so the watchdog can apply it when no render is running.
6. Keep changes backwards compatible and in the existing code style.
7. When finished: move the finished item into the "Done" log in UPGRADES.md with today's date, append any new ideas to "Next", and write a short summary to backend/storage/ops/ai/{day}.md. Then stop.

Work quietly and autonomously. End with a one-paragraph summary of what you changed and the test result.
"""


# ------------------------------------------------------------------ paths/state

def root() -> Path:
    path = Path(settings.STORAGE_PATH) / "ops"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _today() -> str:
    return datetime.now(IST).date().isoformat()


def _markers_path() -> Path:
    return root() / "last.json"


def _cfg_path() -> Path:
    return root() / "config.json"


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        if _cfg_path().is_file():
            cfg.update(json.loads(_cfg_path().read_text(encoding="utf-8")))
    except Exception as exc:
        log.warning("ops config unreadable: %s", exc)
    return cfg


def save_config(patch: dict) -> dict:
    cfg = load_config()
    cfg.update({k: bool(v) for k, v in patch.items() if k in DEFAULT_CONFIG and v is not None})
    try:
        _cfg_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("ops config unwritable: %s", exc)
    return cfg


def _markers() -> dict:
    try:
        if _markers_path().is_file():
            return json.loads(_markers_path().read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _set_marker(kind: str, day: str) -> None:
    m = _markers()
    m[kind] = day
    try:
        _markers_path().write_text(json.dumps(m, indent=2), encoding="utf-8")
    except Exception:
        pass


def last_run(kind: str) -> str | None:
    return _markers().get(kind)


# ------------------------------------------------------------------ maintenance

def backup() -> list[str]:
    """Consistent snapshot of every SQLite database (safe while in use)."""
    dest = root() / "backups" / _today()
    dest.mkdir(parents=True, exist_ok=True)
    storage = Path(settings.STORAGE_PATH)
    saved: list[str] = []
    for db_path in sorted(storage.rglob("*.sqlite3")):
        rel = db_path.relative_to(storage)
        if rel.parts and rel.parts[0] == "ops":
            continue  # never back up our own backups
        name = rel.as_posix().replace("/", "__")
        out = dest / name
        try:
            src = sqlite3.connect(str(db_path), timeout=30)
            dst = sqlite3.connect(str(out))
            with dst:
                src.backup(dst)
            dst.close()
            src.close()
            saved.append(name)
        except Exception as exc:
            log.warning("backup failed for %s: %s", db_path, exc)
    return saved


def write_report(saved_backups: list[str] | None = None, voice: dict | None = None) -> dict:
    from app.voice import agent
    from app import store

    try:
        health = agent.check()
    except Exception as exc:  # pragma: no cover - defensive
        health = {"error": type(exc).__name__}
    try:
        money = store.analytics()
    except Exception as exc:  # pragma: no cover - defensive
        money = {"error": type(exc).__name__}

    voice = voice or {}
    voice_ok = bool(voice.get("ok", True))
    disk_e = health.get("disk_e_gb")
    ok = (bool(disk_e is None or disk_e > 5)
          and bool(health.get("narration_ok", True))
          and voice_ok)
    doc = {
        "day": _today(),
        "at": datetime.now(IST).isoformat(timespec="seconds"),
        "ok": ok,
        "health": health,
        "voice": voice,
        "store": money,
        "backups": saved_backups or [],
    }
    path = root() / "reports" / f"{_today()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("report write failed: %s", exc)
    return doc


def _prune_dirs(parent: Path, keep: int) -> int:
    if not parent.is_dir():
        return 0
    dirs = sorted((d for d in parent.iterdir() if d.is_dir()), key=lambda p: p.name)
    removed = 0
    for old in dirs[:-keep] if len(dirs) > keep else []:
        try:
            shutil.rmtree(old, ignore_errors=True)
            removed += 1
        except Exception:
            pass
    return removed


def prune() -> dict:
    reports = root() / "reports"
    old_reports = 0
    if reports.is_dir():
        files = sorted((f for f in reports.glob("*.json")), key=lambda p: p.name)
        for old in (files[:-_REPORT_KEEP] if len(files) > _REPORT_KEEP else []):
            try:
                old.unlink()
                old_reports += 1
            except Exception:
                pass
    samples = Path(settings.STORAGE_PATH) / "voice"
    old_samples = 0
    cutoff = datetime.now(timezone.utc).timestamp() - _SAMPLE_KEEP_DAYS * 86400
    if samples.is_dir():
        for mp3 in samples.glob("sample-*.mp3"):
            try:
                if mp3.stat().st_mtime < cutoff:
                    mp3.unlink()
                    old_samples += 1
            except Exception:
                pass
    return {"backups": _prune_dirs(root() / "backups", _BACKUP_KEEP),
            "reports": old_reports, "samples": old_samples}


# ------------------------------------------------------------------ voice health

_PROBE_SOURCE = (
    "import asyncio, sys\n"
    "import edge_tts\n"
    "async def main():\n"
    "    await edge_tts.Communicate('\\u0bb5\\u0ba3\\u0b95\\u0bcd\\u0b95\\u0bae\\u0bcd', 'ta-IN-PallaviNeural').save(sys.argv[1])\n"
    "asyncio.run(asyncio.wait_for(main(), 60))\n"
)


def _probe_tts(destination: Path) -> dict:
    """Synthesise one short Tamil phrase in a *fresh* process.

    Running out of process matters: it exercises whatever edge-tts version is on
    disk, which is exactly what the next backend restart will load, rather than
    the (possibly stale) copy already imported in memory.
    """
    script = root() / "_voice_probe.py"
    try:
        script.write_text(_PROBE_SOURCE, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(script), str(destination)],
                              capture_output=True, text=True, timeout=120,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        ok = proc.returncode == 0 and destination.is_file() and destination.stat().st_size > 1000
        detail = "" if ok else (proc.stderr or proc.stdout or "no audio").strip()[-300:]
        return {"ok": ok, "error": None if ok else detail}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


def _edge_tts_version() -> str:
    try:
        import importlib.metadata as md
        return md.version("edge-tts")
    except Exception:
        return ""


def _upgrade_edge_tts() -> dict:
    """Best-effort ``pip install -U edge-tts``; reports whether the version moved."""
    before = _edge_tts_version()
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "edge-tts"],
                              capture_output=True, text=True, timeout=420)
        after = _edge_tts_version()
        return {"ran": True, "before": before, "after": after,
                "changed": bool(after and after != before), "rc": proc.returncode}
    except Exception as exc:  # noqa: BLE001
        return {"ran": False, "before": before, "error": f"{type(exc).__name__}: {exc}"[:300]}


def _request_restart(reason: str) -> None:
    try:
        (root() / "restart.requested").write_text(reason + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("could not request restart: %s", exc)


def voice_check(allow_upgrade: bool = True) -> dict:
    """Prove the Tamil neural voice works; self-heal if it is broken.

    Runs once a day, well before the morning renders. If edge-tts is failing
    (e.g. Microsoft rejects a stale Sec-MS-GEC token) this updates the library
    and, when that fixes it, drops ``restart.requested`` so the watchdog
    reloads the backend at the next safe moment.
    """
    dest = root() / "voice_probe.mp3"
    probe = _probe_tts(dest)
    result = {"ok": probe["ok"], "version": _edge_tts_version(), "error": probe.get("error")}
    if not probe["ok"] and allow_upgrade:
        result["upgrade"] = _upgrade_edge_tts()
        if result["upgrade"].get("changed"):
            again = _probe_tts(dest)
            result.update(ok=again["ok"], after_upgrade_ok=again["ok"],
                          error=again.get("error"), version=_edge_tts_version())
            if again["ok"]:
                _request_restart(f"edge-tts upgraded to {result['version']}")
                result["restart_requested"] = True
    try:
        dest.unlink()
    except Exception:
        pass
    return result


# ------------------------------------------------------------------ self-upgrade

def ai_upgrade(reason: str = "daily") -> dict:
    """Launch one unattended OpenCode session that ships a single safe upgrade."""
    cfg = load_config()
    if not cfg.get("ai_upgrade_enabled", True):
        return {"started": False, "reason": "disabled"}
    if not CLI.exists():
        return {"started": False, "reason": "cli-missing"}
    day = _today()
    logfile = root() / "ai" / f"{day}.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    try:
        fh = logfile.open("a", encoding="utf-8")
        fh.write(f"\n\n===== {datetime.now(IST).isoformat(timespec='seconds')} autonomous upgrade ({reason}) =====\n")
        fh.flush()
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        proc = subprocess.Popen(
            [str(CLI), "run", "--standalone", "--auto", "--model", MODEL,
             AI_PROMPT.format(day=day, project=PROJECT, python=sys.executable,
                              temp=Path(os.environ.get("TEMP", PROJECT / "backend" / "storage")))],
            cwd=str(PROJECT), stdout=fh, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
        )
        _set_marker("ai", day)
        return {"started": True, "pid": proc.pid, "log": logfile.name}
    except Exception as exc:
        log.warning("could not launch autonomous upgrade: %s", exc)
        return {"started": False, "reason": type(exc).__name__}


# ------------------------------------------------------------------ entry points

def maybe_run(force: bool = False) -> dict:
    """Run the daily cycle at most once per IST day (or immediately when forced)."""
    with _LOCK:
        cfg = load_config()
        day = _today()
        result = {"day": day, "ran": False}
        if not force and last_run("daily") == day:
            return result
        if _BUSY.is_set():
            return {"day": day, "ran": False, "reason": "busy"}
        _BUSY.set()
        try:
            saved = backup() if cfg.get("backup_enabled", True) else []
            voice = voice_check() if cfg.get("voice_check_enabled", True) else {}
            doc = write_report(saved, voice) if cfg.get("daily_report_enabled", True) else {}
            pruned = prune()
            _set_marker("daily", day)
            result.update(ran=True, ok=doc.get("ok"), backups=len(saved), pruned=pruned,
                          voice_ok=voice.get("ok"))
            try:
                from app.voice import agent
                if voice and not voice.get("ok"):
                    agent._record("ops", "Tamil voice check failed — trying to fix the speech engine.")
                elif voice.get("restart_requested"):
                    agent._record("ops", "Tamil voice repaired — a restart was requested.")
                agent._record("ops", f"Daily maintenance done — {len(saved)} backups, report {day}.")
            except Exception:
                pass
            if last_run("ai") != day:
                result["upgrade"] = ai_upgrade("daily")
        finally:
            _BUSY.clear()
        return result


def status() -> dict:
    day = _today()
    report_doc = None
    rp = root() / "reports" / f"{day}.json"
    if rp.is_file():
        try:
            report_doc = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            report_doc = None
    ai_log = ""
    lp = root() / "ai" / f"{day}.log"
    if lp.is_file():
        try:
            ai_log = "\n".join(lp.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
        except Exception:
            ai_log = ""
    roadmap = ""
    try:
        roadmap = ROADMAP.read_text(encoding="utf-8")
    except Exception:
        roadmap = ""
    return {
        "day": day,
        "config": load_config(),
        "last_daily": last_run("daily"),
        "last_ai": last_run("ai"),
        "report": report_doc,
        "ai_log": ai_log,
        "roadmap": roadmap,
        "cli": str(CLI),
        "cli_available": CLI.exists(),
        "project": str(PROJECT),
    }
