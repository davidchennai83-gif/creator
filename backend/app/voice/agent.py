"""24x7 voice surveillance agent.

A daemon thread started with the API. Every minute it inspects the platform —
Ollama, the recorder browser, disk space, today's renders (and whether they really
carry narration), the YouTube upload log and pending store orders — and *speaks*
in Tamil through the PC speakers when something changes, or on a heartbeat.
State, config and an event log live under storage/voice so the UI can show them.
"""
import json
import logging
import shutil
import socket
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from app.config.settings import settings
from . import tts
from .narration import day_videos

log = logging.getLogger(__name__)

_LOCK = threading.RLock()
_STARTED = threading.Event()
_STOP = threading.Event()
_RUNS: dict = {}
_EVENTS: list = []
_LAST_HEARTBEAT = {"at": 0.0}
_PREV: dict = {}
_LOOP_SECONDS = 60

DEFAULT_CONFIG = {
    "enabled": True,
    "interval_minutes": 15,
    "voice": tts.DEFAULT_VOICE,
    "speak_heartbeat": True,
    "speak_alerts": True,
}


def root() -> Path:
    path = Path(settings.STORAGE_PATH) / "voice"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cfg_path() -> Path:
    return root() / "config.json"


def _state_path() -> Path:
    return root() / "state.json"


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        if _cfg_path().is_file():
            cfg.update(json.loads(_cfg_path().read_text(encoding="utf-8")))
    except Exception as exc:
        log.warning("voice config unreadable: %s", exc)
    return cfg


def save_config(patch: dict) -> dict:
    cfg = load_config()
    if patch.get("voice") and patch["voice"] not in tts.VOICES:
        patch.pop("voice", None)
    cfg.update({k: v for k, v in patch.items() if k in DEFAULT_CONFIG and v is not None})
    try:
        cfg["interval_minutes"] = max(1, min(720, int(cfg["interval_minutes"])))
    except Exception:
        cfg["interval_minutes"] = DEFAULT_CONFIG["interval_minutes"]
    _cfg_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def disk_free_gb(drive: str):
    try:
        return round(shutil.disk_usage(drive).free / 1_000_000_000, 1)
    except Exception:
        return None


def _youtube_uploads_total() -> int:
    log_file = Path(settings.STORAGE_PATH) / "automation" / "projects" / "YouTube Upload" / "uploaded.log"
    if not log_file.is_file():
        return 0
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return 0
    return sum(1 for line in lines if line.strip())


def _pending_orders() -> int:
    db_path = Path(settings.STORAGE_PATH) / "store" / "orders.sqlite3"
    if not db_path.is_file():
        return 0
    done = {"Delivered", "Cancelled", "Returned"}
    count = 0
    try:
        with sqlite3.connect(str(db_path), timeout=30) as db:
            for (body,) in db.execute("SELECT body FROM orders").fetchall():
                try:
                    if json.loads(body).get("status") not in done:
                        count += 1
                except Exception:
                    continue
    except Exception as exc:
        log.warning("could not read store orders: %s", exc)
    return count


def check() -> dict:
    videos = day_videos()
    done = [v for v in videos if v["status"] == "complete"]
    findings = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "backend": True,
        "ollama": port_open(11434),
        "recorder": port_open(9222),
        "disk_e_gb": disk_free_gb("E:\\"),
        "disk_c_gb": disk_free_gb("C:\\"),
        "videos": videos,
        "renders_total": len(videos),
        "renders_complete": len(done),
        "narration_ok": all(v["has_narration"] for v in done) if done else True,
        "silent_videos": [v["kind"] for v in done if not v["has_narration"]],
        "uploads_today": _youtube_uploads_total(),
        "pending_orders": _pending_orders(),
    }
    return findings


def summarize(f: dict) -> str:
    parts = ["கிரியேட்டர் தளம் கண்காணிப்பு அறிக்கை."]
    parts.append("Ollama இயங்குகிறது." if f["ollama"] else "Ollama நின்றுவிட்டது.")
    parts.append("ரெக்கார்டர் இயங்குகிறது." if f["recorder"] else "ரெக்கார்டர் இயங்கவில்லை.")
    parts.append(f"இன்று {f['renders_complete']} வீடியோ முடிந்தது.")
    if f["renders_complete"] and not f["narration_ok"]:
        parts.append("சில வீடியோவில் குரல் இல்லை.")
    parts.append(f"இதுவரை {f['uploads_today']} வீடியோ பதிவேற்றம் பதிவாகியுள்ளது.")
    if f["pending_orders"]:
        parts.append(f"{f['pending_orders']} ஆர்டர் நிலுவையில் உள்ளது.")
    try:
        from app.growth import agent as growth_agent
        line = growth_agent.speak_line()
        if line:
            parts.append(line)
    except Exception:
        pass
    if f["disk_e_gb"] is not None and f["disk_e_gb"] < 15:
        parts.append(f"எச்சரிக்கை: E டிஸ்க் இடம் {f['disk_e_gb']} ஜிபி மட்டுமே.")
    else:
        parts.append("எல்லாம் சரியாக உள்ளது.")
    return " ".join(parts)


def alerts(f: dict, prev: dict) -> list:
    out = []
    checks = [("ollama", "Ollama", "Ollama மீண்டும் இயங்குகிறது.", "Ollama நின்றுவிட்டது."),
              ("recorder", "ரெக்கார்டர்", "ரெக்கார்டர் மீண்டும் இயங்குகிறது.", "ரெக்கார்டர் நின்றுவிட்டது.")]
    if prev:
        for key, _label, back, gone in checks:
            if prev.get(key) and not f.get(key):
                out.append(gone)
            elif not prev.get(key) and f.get(key):
                out.append(back)
        if f["renders_complete"] > prev.get("renders_complete", 0):
            out.append(f"ஒரு வீடியோ மேலும் முடிந்தது. மொத்தம் {f['renders_complete']}.")
        if f["uploads_today"] > prev.get("uploads_today", 0):
            out.append(f"யூடியூபில் புதிய வீடியோ பதிவேற்றப்பட்டது. மொத்தம் {f['uploads_today']}.")
        if f["pending_orders"] > prev.get("pending_orders", 0):
            out.append(f"புதிய ஆர்டர் வந்துள்ளது. நிலுவை {f['pending_orders']}.")
    if f["disk_e_gb"] is not None and f["disk_e_gb"] < 15:
        if not prev or prev.get("disk_e_gb", 999) >= 15:
            out.append(f"எச்சரிக்கை: E டிரைவ் இடம் {f['disk_e_gb']} ஜிபி மட்டும்.")
    if f["silent_videos"]:
        kinds = ", ".join(f["silent_videos"])
        tag = f"silent:{kinds}"
        if not any(e.get("tag") == tag for e in _EVENTS[-20:]):
            out.append(f"எச்சரிக்கை: {kinds} வீடியோவில் குரல் இல்லை.")
    return out


def _record(kind: str, text: str, **extra):
    event = {"at": datetime.now().isoformat(timespec="seconds"), "kind": kind, "text": text, **extra}
    _EVENTS.append(event)
    del _EVENTS[:-60]
    try:
        with (_event_log()).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return event


def _event_log() -> Path:
    return root() / "agent.log"


def _announce(text: str, kind: str):
    cfg = load_config()
    if not cfg.get("enabled"):
        _record(kind, text, spoken=False, reason="disabled")
        return
    result = tts.speak(text, voice=cfg.get("voice", tts.DEFAULT_VOICE))
    _record(kind, text, spoken=bool(result.get("played")), engine=result.get("engine"))


def tick(force: bool = False) -> dict:
    """One surveillance pass. `force` speaks the summary immediately."""
    with _LOCK:
        cfg = load_config()
        findings = check()
        msgs = alerts(findings, _PREV)
        _PREV.clear()
        _PREV.update(findings)
        first = _LAST_HEARTBEAT["at"] == 0.0
        due = force or first or (time.time() - _LAST_HEARTBEAT["at"]) >= cfg["interval_minutes"] * 60
        if msgs and cfg.get("speak_alerts"):
            _announce(" ".join(msgs), "alert")
            _LAST_HEARTBEAT["at"] = time.time()
        elif due and cfg.get("speak_heartbeat"):
            text = ("கண்காணிப்பு ஏஜென்ட் இயங்கத் தொடங்கிவிட்டது. " + summarize(findings)) if first else summarize(findings)
            _announce(text, "heartbeat")
            _LAST_HEARTBEAT["at"] = time.time()
        state = {"config": cfg, "findings": findings, "events": _EVENTS[-40:], "checked_at": findings["time"]}
        _RUNS.clear()
        _RUNS.update(state)
        try:
            _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return state


def speech_now(text: str, voice=None) -> dict:
    cfg = load_config()
    return tts.speak(text, voice=voice or cfg.get("voice", tts.DEFAULT_VOICE))


def state() -> dict:
    with _LOCK:
        base = dict(_RUNS) if _RUNS else {}
        if not base and _state_path().is_file():
            try:
                base = json.loads(_state_path().read_text(encoding="utf-8"))
            except Exception:
                base = {}
        base["config"] = load_config()  # always live, never the value cached at the last tick
        base.setdefault("findings", None)
        base.setdefault("events", [])
        base.setdefault("checked_at", None)
        return base


def _loop():
    while not _STOP.is_set():
        try:
            tick()
        except Exception:
            log.exception("voice agent tick failed")
        try:
            from app.ops import daily as ops_daily
            ops_daily.maybe_run()
        except Exception:
            log.exception("daily ops failed")
        try:
            from app.growth import agent as growth_agent
            growth_agent.tick()
        except Exception:
            log.exception("growth agent tick failed")
        try:
            from app import finds_agent
            finds_agent.tick()
        except Exception:
            log.exception("Meesho autopilot tick failed")
        _STOP.wait(_LOOP_SECONDS)


def start() -> None:
    if _STARTED.is_set():
        return
    _STARTED.set()
    _STOP.clear()
    _load_events()
    threading.Thread(target=_loop, name="voice-agent", daemon=True).start()
    log.info("voice surveillance agent started (interval %s min)", load_config()["interval_minutes"])


def stop() -> None:
    _STOP.set()


def _load_events():
    if not _event_log().is_file():
        return
    try:
        lines = _event_log().read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        for line in lines:
            try:
                _EVENTS.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
