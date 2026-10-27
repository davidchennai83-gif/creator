"""Meesho Autopilot — the control plane for Tamil Budget Finds.

The existing scheduler already renders the 19:00 Meesho video and the three
upload projects already post it at 19:30 / 19:45 / 20:00. What was missing was a
single place that *chooses* the product, records the whole funnel, and can step
in when a stage fails. This module adds exactly that, without replacing the
battle-tested executor:

    select (18:00) -> approve -> script/render -> publish -> track

It deliberately observes the existing job and uploader logs instead of
re-implementing them. That keeps one source of truth, avoids double posting and
means a scheduler retry is reflected here automatically.

Honesty rules baked in:
* A demo/search product is never described as commissionable.
* ``require_affiliate_link`` can block publishing until a real link exists.
* No fake views, clicks, orders or engagement are created anywhere.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from app import affiliate, finds
from app.config.settings import settings

log = logging.getLogger(__name__)
LOCK = threading.RLock()

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

PLATFORMS = ("youtube", "facebook", "instagram")
PLATFORM_LABEL = {"youtube": "YouTube", "facebook": "Facebook", "instagram": "Instagram"}
PLATFORM_PROJECT = {
    "youtube": "Meesho YouTube Upload",
    "facebook": "Meesho Facebook Upload",
    "instagram": "Meesho Instagram Upload",
}
PLATFORM_LOG = {
    "youtube": ("YouTube Upload", "uploaded.log"),
    "facebook": ("Facebook Upload", "fb_uploaded.log"),
    "instagram": ("Instagram Upload", "ig_uploaded.log"),
}
STAGES = ("discover", "score", "approve", "script", "render", *PLATFORMS, "track")
DEFAULT_TIMES = {"video": "19:00", "youtube": "19:30", "facebook": "19:45", "instagram": "20:00"}

DEFAULT_CONFIG = {
    "enabled": True,
    # Choose + pin the product at 18:00, one hour before the existing 19:00 render.
    "auto_prepare": True,
    "prepare_at": "18:00",
    # False keeps the current hands-off behaviour. True pauses a new day until
    # the owner approves the product in the Autopilot tab.
    "approval_required": False,
    # True blocks publishing demo/search products entirely. Default false so the
    # current sample catalogue keeps flowing while real links are being added.
    "require_affiliate_link": False,
    # The 19:30/19:45/20:00 schedules already publish. When auto_publish is on,
    # the Autopilot becomes a retry layer: it waits for the schedule, then posts
    # any platform that is still missing. It never races a live upload.
    "auto_publish": False,
    # One switch for the owner: select + approve + retry publishing, no clicks.
    "auto_mode": False,
    # Instagram/Facebook are the requested hands-off destinations. YouTube is
    # left to its own schedule because of the unverified-channel daily cap.
    "auto_publish_platforms": ["instagram", "facebook"],
    # Give the existing 19:45/20:00 schedules time to finish before retrying.
    "publish_grace_minutes": 20,
    # Stop retrying a platform after this many real attempts in one day.
    "max_publish_attempts": 2,
    # Optional hands-off catalogue feed: a CSV URL (Google Sheets "publish to
    # web", affiliate network export, etc.) or a local file/folder.
    "feed_url": "",
    "feed_path": "",
    "feed_sync_at": "06:00",
    # "platforms" controls what the run tracks; auto_publish_platforms controls
    # what the retry layer is allowed to post by itself.
    "platforms": list(PLATFORMS),
}

BOOL_KEYS = {"enabled", "auto_prepare", "approval_required", "require_affiliate_link",
             "auto_publish", "auto_mode"}
TIME_KEYS = {"prepare_at", "feed_sync_at"}
INT_KEYS = {"publish_grace_minutes": (0, 180), "max_publish_attempts": (1, 10)}
TEXT_KEYS = {"feed_url", "feed_path"}
LIST_KEYS = {"platforms", "auto_publish_platforms"}


# ---------------------------------------------------------------------------
# Paths, time and config
# ---------------------------------------------------------------------------
def _finds_dir() -> Path:
    path = Path(settings.STORAGE_PATH) / "finds"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _finds_dir() / "agent_state.json"


def _config_path() -> Path:
    return _finds_dir() / "agent_config.json"


def now_ist() -> datetime:
    return datetime.now(IST)


def today() -> str:
    return now_ist().date().isoformat()


def _parse_day(value=None) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    if not text:
        return today()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("Day must be YYYY-MM-DD") from exc


def _iso_day_ist(value: str | None) -> str:
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment.astimezone(IST).date().isoformat()
    except ValueError:
        return str(value)[:10]


def _parse_hhmm(value: str, fallback: str) -> str:
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", str(value or "").strip())
    return value.strip() if match else fallback


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        if _config_path().is_file():
            saved = json.loads(_config_path().read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in DEFAULT_CONFIG})
    except Exception as exc:
        log.warning("Autopilot config unreadable: %s", exc)
    cfg["platforms"] = [p for p in cfg.get("platforms") or PLATFORMS if p in PLATFORMS]
    cfg["auto_publish_platforms"] = [
        p for p in cfg.get("auto_publish_platforms") or ["instagram", "facebook"]
        if p in PLATFORMS
    ]
    for key in TIME_KEYS:
        cfg[key] = _parse_hhmm(cfg.get(key), DEFAULT_CONFIG[key])
    for key, (low, high) in INT_KEYS.items():
        try:
            cfg[key] = max(low, min(high, int(cfg.get(key) or DEFAULT_CONFIG[key])))
        except (TypeError, ValueError):
            cfg[key] = DEFAULT_CONFIG[key]
    for key in TEXT_KEYS:
        cfg[key] = str(cfg.get(key) or "").strip()[:2000]
    return cfg


def save_config(patch: dict) -> dict:
    cfg = load_config()
    for key, default in DEFAULT_CONFIG.items():
        if key not in patch or patch[key] is None:
            continue
        value = patch[key]
        if key in LIST_KEYS:
            chosen = [p for p in value if p in PLATFORMS] if isinstance(value, list) else []
            if chosen:
                cfg[key] = chosen
        elif key in TIME_KEYS:
            cfg[key] = _parse_hhmm(value, default)
        elif key in INT_KEYS:
            low, high = INT_KEYS[key]
            try:
                cfg[key] = max(low, min(high, int(value)))
            except (TypeError, ValueError):
                pass
        elif key in TEXT_KEYS:
            text = str(value or "").strip()[:2000]
            if key == "feed_url" and text and not text.lower().startswith(("http://", "https://")):
                raise ValueError("Feed URL must start with http:// or https://")
            cfg[key] = text
        elif key in BOOL_KEYS or isinstance(default, bool):
            cfg[key] = bool(value)
    # One switch for the owner: autonomy means no approval click and a retry
    # layer for publishing. Affiliate-link strictness stays an explicit choice.
    if cfg.get("auto_mode"):
        cfg["auto_prepare"] = True
        cfg["approval_required"] = False
        cfg["auto_publish"] = True
    elif "auto_mode" in patch and not patch.get("auto_mode"):
        # Turning autonomy off should stop unattended posting, not silently keep
        # the retry layer armed.
        cfg["auto_publish"] = False
        cfg["approval_required"] = True
    _config_path().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


# ---------------------------------------------------------------------------
# Run store (same SQLite file as finds; no main-app schema changes)
# ---------------------------------------------------------------------------
def _connect() -> sqlite3.Connection:
    _finds_dir()
    db = sqlite3.connect(str(finds.DB), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            day TEXT NOT NULL,
            product_id TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            stage TEXT NOT NULL DEFAULT 'discover',
            approved INTEGER NOT NULL DEFAULT 0,
            job_id TEXT,
            stages TEXT NOT NULL DEFAULT '{}',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_agent_runs_day ON agent_runs(day);
        CREATE TABLE IF NOT EXISTS agent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            at TEXT NOT NULL,
            event TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS ix_agent_events_run ON agent_events(run_id, id);
        """
    )
    return db


def _empty_stages() -> dict:
    return {stage: {"status": "pending", "at": "", "detail": ""} for stage in STAGES}


def _parse_stages(raw) -> dict:
    stages = _empty_stages()
    try:
        saved = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (TypeError, ValueError):
        saved = {}
    if isinstance(saved, dict):
        for stage in STAGES:
            item = saved.get(stage)
            if isinstance(item, str):
                stages[stage] = {"status": item, "at": "", "detail": ""}
            elif isinstance(item, dict):
                stages[stage] = {
                    "status": str(item.get("status") or "pending"),
                    "at": str(item.get("at") or ""),
                    "detail": str(item.get("detail") or ""),
                }
    return stages


def _set_stage(stages: dict, stage: str, status: str, detail: str = "") -> bool:
    current = stages.setdefault(stage, {"status": "pending", "at": "", "detail": ""})
    changed = current.get("status") != status or (detail and detail != current.get("detail"))
    if changed:
        current.update(status=status, at=now_ist().isoformat(timespec="seconds"),
                       detail=str(detail or "")[:800])
    return changed


def _row_run(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    data = dict(row)
    data["approved"] = bool(data.get("approved"))
    data["stages"] = _parse_stages(data.get("stages"))
    return data


def _event(db: sqlite3.Connection, run_id: str, event: str, detail: str = "") -> None:
    db.execute(
        "INSERT INTO agent_events (run_id, at, event, detail) VALUES (?,?,?,?)",
        (str(run_id), now_ist().isoformat(timespec="seconds"), str(event)[:80], str(detail)[:1000]),
    )


def _create_run(db: sqlite3.Connection, day: str, product_id: str | None) -> dict:
    run_id = str(uuid5(NAMESPACE_URL, f"finds-agent:{day}"))
    row = db.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
    if row:
        return _row_run(row)
    stamp = now_ist().isoformat(timespec="seconds")
    stages = _empty_stages()
    db.execute(
        "INSERT INTO agent_runs (id, day, product_id, status, stage, approved, job_id, stages, note, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, day, product_id, "planned", "discover", 0, None,
         json.dumps(stages, ensure_ascii=False), "", stamp, stamp),
    )
    _event(db, run_id, "run_created", f"Autopilot run created for {day}")
    return _row_run(db.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone())


def get_run(day: str | None = None, run_id: str | None = None) -> dict | None:
    with _connect() as db:
        if run_id:
            row = db.execute("SELECT * FROM agent_runs WHERE id=?", (str(run_id),)).fetchone()
        else:
            row = db.execute("SELECT * FROM agent_runs WHERE day=? ORDER BY created_at DESC LIMIT 1",
                             (_parse_day(day),)).fetchone()
    return _row_run(row)


def list_runs(limit: int = 20) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with _connect() as db:
        rows = db.execute("SELECT * FROM agent_runs ORDER BY day DESC, created_at DESC LIMIT ?",
                          (limit,)).fetchall()
    return [_row_run(row) for row in rows]


def list_events(run_id: str | None = None, limit: int = 30) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with _connect() as db:
        if run_id:
            rows = db.execute("SELECT * FROM agent_events WHERE run_id=? ORDER BY id DESC LIMIT ?",
                              (str(run_id), limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM agent_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def _update_run(run_id: str, **fields) -> dict | None:
    allowed = {"product_id", "status", "stage", "approved", "job_id", "stages", "note"}
    values = {k: v for k, v in fields.items() if k in allowed}
    if not values:
        return get_run(run_id=run_id)
    values["updated_at"] = now_ist().isoformat(timespec="seconds")
    if "approved" in values:
        values["approved"] = 1 if values["approved"] else 0
    if "stages" in values and not isinstance(values["stages"], str):
        values["stages"] = json.dumps(values["stages"], ensure_ascii=False)
    assignments = ", ".join(f"{key}=?" for key in values)
    with _connect() as db:
        db.execute(f"UPDATE agent_runs SET {assignments} WHERE id=?",
                   (*values.values(), str(run_id)))
        _event(db, run_id, "run_updated", values.get("status") or "updated")
        db.commit()
    return get_run(run_id=run_id)


# ---------------------------------------------------------------------------
# Selection, monetisation and recommendations
# ---------------------------------------------------------------------------
def _performance_bonus(product: dict) -> float:
    orders = float(product.get("orders") or 0)
    clicks = float(product.get("clicks") or 0)
    earned = float(product.get("commission_earned") or 0)
    return min(12.0, orders * 2.0 + clicks * 0.15 + earned * 0.05)


def _freshness_penalty(product: dict, day: str) -> float:
    last = _iso_day_ist(product.get("last_used_at"))
    if not last:
        return 0.0
    try:
        age = (date.fromisoformat(day) - date.fromisoformat(last)).days
    except ValueError:
        return 0.0
    if age <= 0:
        return 30.0
    if age < 3:
        return 14.0
    if age < 7:
        return 6.0
    return 0.0


def candidate_score(product: dict, day: str) -> float:
    base = float(product.get("score") or 0)
    # Once real affiliate links exist, they should outrank samples. Samples can
    # still flow while the catalogue is being built, but never win by default.
    money = monetization(product)
    if money["ready"]:
        base += 15.0
    elif money["demo"]:
        base -= 4.0
    return round(max(0.0, base + _performance_bonus(product) - _freshness_penalty(product, day)), 2)


def monetization(product: dict | None) -> dict:
    """Is this product actually commissionable? Never guess in the UI.

    A plain Amazon/Flipkart/Meesho product URL is not commissionable until it
    carries a tracking token or the owner explicitly verified it. Link-wrapper
    networks (EarnKaro, Cuelinks, INRDeals...) are commissionable by design.
    """
    if not product:
        return {"ready": False, "issues": ["No product selected"], "warnings": [],
                "demo": False, "commission_percent": 0, "host": "",
                "network": "", "network_label": "", "wrapper": False}
    url = str(product.get("affiliate_url") or "").strip()
    host = urlparse(url).netloc.lower()
    demo = bool(product.get("demo"))
    commission = float(product.get("commission_percent") or 0)
    result = affiliate.check(
        url, demo=demo, commission_percent=commission,
        price=float(product.get("price") or 0),
        verified=bool(product.get("affiliate_verified")),
    )
    issues = list(result["issues"])
    warnings = list(result["warnings"])
    if not product.get("image_url"):
        warnings.append("Product image is missing (the video will use a text card)")
    if not product.get("features"):
        warnings.append("No benefit bullets yet (AI copy will use safe defaults)")
    return {
        "ready": not issues,
        "issues": issues,
        "warnings": warnings,
        "demo": demo,
        "commission_percent": commission,
        "host": host,
        "network": result["network"],
        "network_label": result["label"],
        "wrapper": result["wrapper"],
    }


def _public_product(product: dict | None, day: str) -> dict | None:
    if not product:
        return None
    data = dict(product)
    data["candidate_score"] = candidate_score(product, day)
    data["monetization"] = monetization(product)
    return data


def recommendations(day: str | None = None, limit: int = 5) -> list[dict]:
    day = _parse_day(day)
    products = finds.list_products(active_only=True, limit=1000)
    pinned = finds.pinned_product(day)
    ranked = sorted(products, key=lambda p: candidate_score(p, day), reverse=True)
    if pinned and pinned.get("active"):
        ranked = [p for p in ranked if p["id"] != pinned["id"]]
        ranked.insert(0, pinned)
    output = []
    for index, product in enumerate(ranked[:max(1, min(int(limit), 20))]):
        item = _public_product(product, day)
        item["recommended"] = index == 0
        item["reason"] = _reason(product, day)
        output.append(item)
    return output


def _reason(product: dict, day: str) -> str:
    bits = []
    discount = product.get("discount_percent") or 0
    rating = product.get("rating") or 0
    orders = product.get("orders_count") or 0
    if discount:
        bits.append(f"{int(discount)}% off")
    if rating:
        bits.append(f"{rating}★")
    if orders:
        bits.append(f"{int(orders):,} orders")
    if product.get("orders") or product.get("clicks"):
        bits.append(f"past: {int(product.get('orders') or 0)} orders / {int(product.get('clicks') or 0)} clicks")
    if not bits:
        bits.append(f"score {product.get('score', 0)}")
    return " · ".join(bits)


def best_product(day: str | None = None) -> dict | None:
    day = _parse_day(day)
    cfg = load_config()
    guard = bool(cfg.get("require_affiliate_link"))
    pinned = finds.pinned_product(day)
    if pinned and pinned.get("active") and (not guard or monetization(pinned)["ready"]):
        return pinned
    ranked = recommendations(day, limit=20)
    if guard:
        ranked = [item for item in ranked if item.get("monetization", {}).get("ready")]
    if not ranked:
        return None
    return finds.get_product(ranked[0]["id"])


def best_ready_product(day: str | None = None) -> dict | None:
    """Best product that is commission-ready, ignoring a sample pin."""
    day = _parse_day(day)
    for item in recommendations(day, limit=20):
        if item.get("monetization", {}).get("ready"):
            return finds.get_product(item["id"])
    return None


# ---------------------------------------------------------------------------
# Existing scheduler + uploader observation
# ---------------------------------------------------------------------------
def _jobs_db() -> Path:
    return Path(settings.STORAGE_PATH) / "video_creator" / "jobs.sqlite3"


def _job_for_day(day: str) -> dict | None:
    db_path = _jobs_db()
    if not db_path.is_file():
        return None
    found = []
    try:
        with sqlite3.connect(str(db_path), timeout=20) as db:
            for (body,) in db.execute("SELECT body FROM jobs ORDER BY rowid DESC").fetchall():
                try:
                    job = json.loads(body)
                except (TypeError, ValueError):
                    continue
                if str(job.get("kind") or "") == "meesho" and str(job.get("date") or "") == day:
                    found.append(job)
    except sqlite3.DatabaseError as exc:
        log.warning("Autopilot could not read video jobs: %s", exc)
        return None
    if not found:
        return None
    priority = {"complete": 5, "rendering": 4, "review": 3, "writing": 3, "new": 2, "failed": 1}
    return max(found, key=lambda job: priority.get(str(job.get("status")), 0))


def _posted_platforms(job_id: str | None) -> dict[str, bool]:
    posted = {platform: False for platform in PLATFORMS}
    if not job_id:
        return posted
    base = Path(settings.AUTOMATION_PATH) / "projects"
    needle = str(job_id)
    for platform, (project, log_name) in PLATFORM_LOG.items():
        log_file = base / project / log_name
        if not log_file.is_file():
            continue
        try:
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]
        except OSError:
            continue
        if any(needle in line for line in lines):
            posted[platform] = True
    return posted


def _publish_attempts(run_id: str, platform: str, day: str) -> int:
    """Count real publish starts today for one platform (manual + automatic)."""
    start = datetime.combine(date.fromisoformat(day), dtime.min, tzinfo=IST).isoformat()
    with _connect() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM agent_events WHERE run_id=? AND event=? AND at>=?",
            (str(run_id), f"publish_{platform}", start),
        ).fetchone()
    return int(row[0] or 0)


def _schedule_rows() -> list[dict]:
    db_path = Path(settings.STORAGE_PATH) / "video_creator" / "schedules.sqlite3"
    if not db_path.is_file():
        return []
    rows = []
    try:
        with sqlite3.connect(str(db_path), timeout=20) as db:
            for (body,) in db.execute("SELECT body FROM schedules").fetchall():
                try:
                    rows.append(json.loads(body))
                except (TypeError, ValueError):
                    continue
    except sqlite3.DatabaseError as exc:
        log.warning("Autopilot could not read schedules: %s", exc)
    return rows


def schedule_map() -> dict:
    result = {key: {"run_time": value, "enabled": False, "owner": None, "voice": None}
              for key, value in DEFAULT_TIMES.items()}
    project_to_key = {"meesho": "video", **{f"automation:{name}": key
                                           for key, name in PLATFORM_PROJECT.items()}}
    for task in _schedule_rows():
        key = project_to_key.get(str(task.get("project") or ""))
        if not key:
            continue
        result[key] = {
            "run_time": str(task.get("run_time") or DEFAULT_TIMES[key]),
            "enabled": bool(task.get("enabled")),
            "owner": task.get("owner"),
            "voice": task.get("voice"),
        }
    return result


def _owner_for(project: str) -> str | None:
    for task in _schedule_rows():
        if str(task.get("project") or "") == f"automation:{project}":
            return task.get("owner")
    return None


def _due_at(day: str, hhmm: str) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    return datetime.combine(date.fromisoformat(day), dtime(hour, minute), tzinfo=IST)


def _metrics(product_id: str | None, day: str) -> dict:
    if not product_id:
        return {"clicks": 0, "orders": 0, "sales": 0.0, "commission": 0.0,
                "all_time_clicks": 0, "all_time_orders": 0, "all_time_commission": 0.0}
    start = datetime.combine(date.fromisoformat(day), dtime.min, tzinfo=IST).astimezone(UTC).isoformat()
    end = (datetime.combine(date.fromisoformat(day), dtime.min, tzinfo=IST) +
           timedelta(days=1)).astimezone(UTC).isoformat()
    with _connect() as db:
        clicks = db.execute(
            "SELECT COUNT(*) FROM clicks WHERE product_id=? AND clicked_at>=? AND clicked_at<?",
            (str(product_id), start, end)).fetchone()[0]
        row = db.execute(
            "SELECT COUNT(*) AS orders, COALESCE(SUM(sale_amount),0) AS sales, "
            "COALESCE(SUM(commission),0) AS commission FROM orders "
            "WHERE product_id=? AND COALESCE(ordered_at, created_at)>=? "
            "AND COALESCE(ordered_at, created_at)<?",
            (str(product_id), start, end)).fetchone()
    product = finds.get_product(product_id) or {}
    return {
        "clicks": int(clicks or 0),
        "orders": int(row["orders"] or 0),
        "sales": round(float(row["sales"] or 0), 2),
        "commission": round(float(row["commission"] or 0), 2),
        "all_time_clicks": int(product.get("clicks") or 0),
        "all_time_orders": int(product.get("orders") or 0),
        "all_time_commission": round(float(product.get("commission_earned") or 0), 2),
    }


# ---------------------------------------------------------------------------
# Reconcile a run against the real job + uploader logs
# ---------------------------------------------------------------------------
def reconcile(day: str | None = None, run: dict | None = None) -> dict | None:
    day = _parse_day(day)
    run = run or get_run(day)
    if not run:
        return None
    stages = run["stages"]
    job = None
    if run.get("job_id"):
        job = next((item for item in [_job_for_day(day)]
                    if item and item.get("id") == run["job_id"]), None)
    if not job:
        job = _job_for_day(day)
    job_id = job.get("id") if job else run.get("job_id")
    posted = _posted_platforms(job_id)
    changed = False
    product_changed = False

    # The job body is the ground truth: it records the product that was actually
    # rendered. This keeps the run correct even if the product was changed after
    # selection, or approval arrived after the 19:00 render.
    job_product_id = None
    if job:
        for point in job.get("points") or []:
            if isinstance(point, dict) and point.get("product_id"):
                job_product_id = str(point["product_id"])
                break
    if job_product_id and job_product_id != run.get("product_id"):
        run["product_id"] = job_product_id
        product_changed = True

    if not stages["discover"].get("at") or product_changed:
        changed |= _set_stage(
            stages, "discover", "done",
            f"Rendered product {run.get('product_id')}" if job_product_id
            else f"Product {run.get('product_id') or 'not selected'}")
    if not stages["score"].get("at") or product_changed:
        product = finds.get_product(run["product_id"]) if run.get("product_id") else None
        if product:
            mon = monetization(product)
            detail = f"score {candidate_score(product, day)} · " + ("commissionable" if mon["ready"] else "; ".join(mon["issues"]))
        else:
            detail = "No product attached"
        changed |= _set_stage(stages, "score", "done", detail)

    changed |= _set_stage(stages, "approve", "done" if run.get("approved") else "pending",
                          "Approved" if run.get("approved") else "Waiting for owner approval")

    status = run.get("status") or "planned"
    note = run.get("note") or ""
    if job:
        job_status = str(job.get("status") or "")
        message = str(job.get("message") or "")
        if job_status in ("writing", "new"):
            changed |= _set_stage(stages, "script", "running", message or "Writing the Tamil script")
        elif job_status in ("review", "rendering", "complete"):
            changed |= _set_stage(stages, "script", "done", "Script ready")
        if job_status == "review":
            changed |= _set_stage(stages, "render", "pending", "Waiting to render")
        elif job_status == "rendering":
            changed |= _set_stage(stages, "render", "running", message or "Rendering the video")
        elif job_status == "complete":
            changed |= _set_stage(stages, "render", "done", "MP4 ready")
        elif job_status == "failed":
            failed_stage = "script" if "script" in message.lower() else "render"
            changed |= _set_stage(stages, failed_stage, "failed", message or "Video generation failed")
            note = message or "Video generation failed"
    for platform in PLATFORMS:
        if posted.get(platform):
            changed |= _set_stage(stages, platform, "done", f"Posted to {PLATFORM_LABEL[platform]}")
        elif job and job.get("status") == "complete":
            # Leave a successfully posted platform alone; only reset a stale "running".
            if stages[platform].get("status") == "running":
                changed |= _set_stage(stages, platform, "pending", "Upload finished without a matching log entry")

    metrics = _metrics(run.get("product_id"), day)
    changed |= _set_stage(
        stages, "track", "done",
        f"{metrics['clicks']} clicks · {metrics['orders']} orders · ₹{metrics['commission']:,.0f}")

    requested = load_config().get("platforms") or list(PLATFORMS)
    if job and job.get("status") == "failed":
        status = "failed"
    elif job and job.get("status") == "complete":
        if all(posted.get(p) for p in requested):
            status = "live"
        elif any(posted.get(p) for p in requested):
            status = "partial"
        else:
            status = "ready_to_publish"
    elif job:
        status = "rendering" if job.get("status") == "rendering" else "script_ready"
    elif run.get("approved"):
        status = "ready"
    elif load_config().get("approval_required"):
        status = "awaiting_approval"
    else:
        status = "planned"

    stage = "track"
    for name in STAGES[:-1]:
        if stages[name].get("status") not in ("done", "skipped"):
            stage = name
            break

    if (changed or product_changed or status != run.get("status") or stage != run.get("stage")
            or note != run.get("note") or job_id != run.get("job_id")):
        with _connect() as db:
            db.execute(
                "UPDATE agent_runs SET product_id=?, status=?, stage=?, job_id=?, stages=?, note=?, updated_at=? WHERE id=?",
                (run.get("product_id"), status, stage, job_id, json.dumps(stages, ensure_ascii=False), note,
                 now_ist().isoformat(timespec="seconds"), run["id"]))
            if status != run.get("status"):
                _event(db, run["id"], f"status_{status}", note or status)
            db.commit()
        run = get_run(run_id=run["id"])
    return run


# ---------------------------------------------------------------------------
# Actions: prepare, approve, publish
# ---------------------------------------------------------------------------
def prepare(day: str | None = None, force: bool = False, product_id: str | None = None) -> dict:
    day = _parse_day(day)
    cfg = load_config()
    existing = get_run(day)
    if existing and not force and not product_id:
        return reconcile(day, existing) or existing

    job = _job_for_day(day)
    if force and not product_id and not job:
        # "Auto-pick" should be able to replace an older manual pin.
        finds.unpin_product(day)
    if product_id:
        if job:
            raise ValueError("Today's video already exists; choose a product for a future day.")
        product = finds.get_product(str(product_id))
        if not product or not product.get("active"):
            raise ValueError("Chosen product was not found or is inactive")
    elif job:
        # The scheduler already chose the product for this day.
        product = finds.today_pick(date.fromisoformat(day))
    else:
        product = best_product(day)
    if not product:
        if cfg.get("require_affiliate_link"):
            raise ValueError("No commission-ready product. Add a real affiliate link and commission % first.")
        raise ValueError("No active Meesho products. Add products or import an affiliate CSV first.")

    mon = monetization(product)
    if cfg.get("require_affiliate_link") and not mon["ready"] and not job:
        raise ValueError("This product has no real affiliate link. Add one or turn off the publishing guard.")
    approved = not cfg.get("approval_required")
    if approved and not job:
        finds.pin_product(day, product["id"], "Autopilot selection")
    note = "" if mon["ready"] else "; ".join(mon["issues"])

    with _connect() as db:
        run = _create_run(db, day, product["id"])
        stages = run["stages"]
        _set_stage(stages, "discover", "done", f"Selected {product.get('title') or product['id']}")
        _set_stage(stages, "score", "done",
                   f"score {candidate_score(product, day)} · " + ("commissionable" if mon["ready"] else note))
        _set_stage(stages, "approve", "done" if approved else "pending",
                   "Approved automatically" if approved else "Waiting for owner approval")
        status = "ready" if approved else "awaiting_approval"
        db.execute(
            "UPDATE agent_runs SET product_id=?, approved=?, status=?, stage=?, stages=?, note=?, updated_at=? WHERE id=?",
            (product["id"], 1 if approved else 0, status,
             "approve" if not approved else "script", json.dumps(stages, ensure_ascii=False),
             note, now_ist().isoformat(timespec="seconds"), run["id"]))
        _event(db, run["id"], "prepared",
               f"Selected {product.get('title') or product['id']}" + (f" — {note}" if note else ""))
        db.commit()
    return reconcile(day) or get_run(day)


def approve(run_id: str, approved: bool = True) -> dict:
    run = get_run(run_id=run_id)
    if not run:
        raise ValueError("Autopilot run not found")
    with _connect() as db:
        db.execute("UPDATE agent_runs SET approved=?, updated_at=? WHERE id=?",
                   (1 if approved else 0, now_ist().isoformat(timespec="seconds"), run["id"]))
        _event(db, run["id"], "approved" if approved else "approval_revoked",
               "Owner approved the product" if approved else "Owner revoked approval")
        db.commit()
    run = get_run(run_id=run_id)
    if approved:
        job = _job_for_day(run["day"])
        if job:
            # Approval arrived after the render: track the product that is
            # actually in the MP4, not the one that was proposed at 18:00.
            actual = finds.today_pick(date.fromisoformat(run["day"]))
            if actual and actual.get("id") != run.get("product_id"):
                _update_run(run["id"], product_id=actual["id"], note="Approved after render; tracking the rendered product")
                run = get_run(run_id=run_id)
        elif run.get("product_id"):
            try:
                finds.pin_product(run["day"], run["product_id"], "Owner approved in Autopilot")
            except ValueError:
                pass
    return reconcile(run["day"], run)


def publish(run_id: str, platform: str | None = None, force: bool = False) -> dict:
    platform = str(platform or "").strip().lower()
    if platform and platform not in PLATFORMS:
        raise ValueError("Platform must be youtube, facebook or instagram")
    run = get_run(run_id=run_id)
    if not run:
        raise ValueError("Autopilot run not found")
    run = reconcile(run["day"], run)
    cfg = load_config()

    job = _job_for_day(run["day"])
    if not job or job.get("status") != "complete":
        return {"ok": False, "blocked": "Today's Meesho video is not rendered yet", "run": run}
    if cfg.get("approval_required") and not run.get("approved"):
        return {"ok": False, "blocked": "This run is waiting for owner approval", "run": run}
    product = finds.get_product(run["product_id"]) if run.get("product_id") else None
    if not product:
        return {"ok": False, "blocked": "No product attached to this run", "run": run}
    if cfg.get("require_affiliate_link") and not monetization(product)["ready"]:
        return {"ok": False, "blocked": "A real affiliate link is required before publishing", "run": run}

    posted = _posted_platforms(job.get("id"))
    missing = [p for p in (cfg.get("platforms") or PLATFORMS) if not posted.get(p)]
    if not platform:
        if not missing:
            return {"ok": True, "skipped": "All social platforms are already posted", "run": run}
        platform = missing[0]
    if platform not in (cfg.get("platforms") or PLATFORMS):
        return {"ok": False, "blocked": f"{PLATFORM_LABEL[platform]} is disabled in Autopilot config", "run": run}
    if posted.get(platform) and not force:
        return {"ok": True, "skipped": f"{PLATFORM_LABEL[platform]} already has this video", "run": run}

    from app.automation import runner
    if runner.gate.locked():
        return {"ok": False, "blocked": "Another upload is already running; try again in a minute", "run": run}
    owner = _owner_for(PLATFORM_PROJECT[platform]) or "finds-agent"
    try:
        automation_run = runner.run(owner, PLATFORM_PROJECT[platform], "main.py")
    except Exception as exc:
        return {"ok": False, "blocked": f"Could not start {PLATFORM_LABEL[platform]}: {exc}", "run": run}
    stages = run["stages"]
    _set_stage(stages, platform, "running", f"Started {PLATFORM_LABEL[platform]} upload")
    with _connect() as db:
        db.execute("UPDATE agent_runs SET status='publishing', stages=?, updated_at=? WHERE id=?",
                   (json.dumps(stages, ensure_ascii=False), now_ist().isoformat(timespec="seconds"),
                    run["id"]))
        _event(db, run["id"], f"publish_{platform}",
               f"Started {PLATFORM_LABEL[platform]} automation {automation_run.get('id')}")
        db.commit()
    return {"ok": True, "platform": platform, "automation_run": automation_run,
            "run": get_run(run_id=run["id"])}


def publish_next(run_id: str) -> dict:
    run = get_run(run_id=run_id)
    if not run:
        raise ValueError("Autopilot run not found")
    return publish(run_id, None)


# ---------------------------------------------------------------------------
# Background tick
# ---------------------------------------------------------------------------
def _write_state(payload: dict) -> None:
    try:
        _state_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Autopilot state unwritable: %s", exc)


def _prune() -> None:
    cutoff = (now_ist() - timedelta(days=180)).date().isoformat()
    with _connect() as db:
        old = [row[0] for row in db.execute("SELECT id FROM agent_runs WHERE day < ?", (cutoff,))]
        if old:
            db.executemany("DELETE FROM agent_runs WHERE id=?", [(run_id,) for run_id in old])
            db.executemany("DELETE FROM agent_events WHERE run_id=?", [(run_id,) for run_id in old])
            db.commit()


def tick() -> dict:
    """One safe pass. Idempotent; never duplicates a render or an upload."""
    cfg = load_config()
    if not cfg.get("enabled"):
        return {"skipped": "disabled"}
    actions = []
    with LOCK:
        _prune()
        for offset in range(3):
            day = (now_ist().date() - timedelta(days=offset)).isoformat()
            run = get_run(day)
            if run:
                reconcile(day, run)

        day = today()
        moment = now_ist()
        run = get_run(day)

        # 1. Refill the catalogue from the configured feed. Once a day is enough;
        # the hash check makes an accidental extra run harmless.
        if cfg.get("feed_url") or cfg.get("feed_path") or any(_feed_dir().iterdir()):
            feed_due = _due_at(day, cfg.get("feed_sync_at") or "06:00")
            last_sync = _read_feed_state().get("last_sync") or ""
            if moment >= feed_due and _iso_day_ist(last_sync) != day:
                try:
                    synced = sync_feed()
                    actions.append({"action": "feed_sync", "imported": synced.get("imported", 0),
                                    "errors": synced.get("error_count", 0)})
                except Exception as exc:
                    log.warning("Feed sync failed: %s", exc)
                    actions.append({"action": "feed_sync_failed", "error": str(exc)})

        # 2. Select a product before the 19:00 render.
        if not run and cfg.get("auto_prepare"):
            prepare_at = _due_at(day, cfg.get("prepare_at") or "18:00")
            if moment >= prepare_at:
                try:
                    run = prepare(day)
                    actions.append({"action": "prepare", "day": day,
                                    "run_id": run.get("id") if run else None})
                except Exception as exc:
                    log.warning("Autopilot prepare failed: %s", exc)
                    actions.append({"action": "prepare_failed", "error": str(exc)})

        # 3. In strict mode, replace a sample pin with a commission-ready find
        # before the render. This is what makes a newly imported feed take over
        # without the owner clicking Auto-pick.
        job = _job_for_day(day)
        if run and not run.get("job_id") and not job:
            product = finds.get_product(run["product_id"]) if run.get("product_id") else None
            should_repick = bool(
                product and (
                    (cfg.get("require_affiliate_link") and not monetization(product)["ready"])
                    or (cfg.get("auto_mode") and product.get("demo"))
                )
            )
            if should_repick:
                try:
                    replacement = best_ready_product(day)
                    if replacement and replacement["id"] != product["id"]:
                        run = prepare(day, force=True, product_id=replacement["id"])
                        actions.append({"action": "repick", "day": day,
                                        "product_id": run.get("product_id") if run else None})
                except Exception as exc:
                    log.warning("Autopilot re-pick failed: %s", exc)
                    actions.append({"action": "repick_failed", "error": str(exc)})

        # 4. An earlier approval pause should not survive the owner enabling
        # zero-touch mode.
        if run and not run.get("approved") and not cfg.get("approval_required"):
            run = approve(run["id"], True)
            actions.append({"action": "auto_approve", "run_id": run.get("id")})

        # 5. Retry only the platforms that are still missing after their normal
        # schedule. The grace window prevents racing the 19:30/19:45/20:00 jobs.
        if cfg.get("auto_publish") or cfg.get("auto_mode"):
            run = get_run(day) or run
            job = _job_for_day(day)
            if not run and job:
                try:
                    run = prepare(day)
                except Exception as exc:
                    log.warning("Autopilot could not adopt today's job: %s", exc)
            if run and job and job.get("status") == "complete":
                schedule = schedule_map()
                posted = _posted_platforms(job.get("id"))
                grace = timedelta(minutes=int(cfg.get("publish_grace_minutes") or 0))
                max_attempts = int(cfg.get("max_publish_attempts") or 1)
                for platform in cfg.get("auto_publish_platforms") or ("instagram", "facebook"):
                    if platform not in (cfg.get("platforms") or PLATFORMS) or posted.get(platform):
                        continue
                    due = _due_at(day, schedule.get(platform, {}).get("run_time")
                                  or DEFAULT_TIMES[platform]) + grace
                    if moment < due:
                        continue
                    if _publish_attempts(run["id"], platform, day) >= max_attempts:
                        actions.append({"action": "publish_gave_up", "platform": platform,
                                        "detail": f"{max_attempts} attempts already used"})
                        continue
                    result = publish(run["id"], platform)
                    actions.append({"action": "publish", "platform": platform,
                                    "ok": result.get("ok"), "blocked": result.get("blocked"),
                                    "skipped": result.get("skipped")})
                    break

        run = get_run(day)
        _write_state({
            "last_tick": moment.isoformat(timespec="seconds"),
            "day": day,
            "run_id": run.get("id") if run else None,
            "status": run.get("status") if run else None,
            "feed": feed_status(),
            "actions": actions,
        })
    return {"day": day, "run": run, "actions": actions, "config": cfg}


# ---------------------------------------------------------------------------
# Link importer (browser-free discovery)
# ---------------------------------------------------------------------------
_LINK_RE = re.compile(r"https?://[^\s|,]+", re.IGNORECASE)


def _humanise_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    tail = path.split("/")[-1] if path else ""
    text = re.sub(r"[-_]+", " ", tail).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) < 4:
        return "Meesho find"
    return text[:120].title()


def _looks_real_affiliate(url: str) -> bool:
    return affiliate.is_affiliate_link(url)


def import_links(text: str, real: bool = False, category: str = "General") -> dict:
    """Import one affiliate product link per line.

    Formats (fields separated by ``|``)::

        https://www.meesho.com/product/...
        Title | https://www.amazon.in/dp/...?...tag=yourtag | 399 | 999 | Kitchen
        Title | URL | price | mrp | category | commission_percent | image_url

    Supported shops: Meesho, Amazon, Flipkart, Myntra, AJIO, Tata CLiQ,
    Snapdeal and the link-conversion networks EarnKaro, Cuelinks, INRDeals,
    vCommission, Admitad, Impact and Optimise. A plain product URL is marked
    ``demo`` unless it has a tracking token or ``real=True``; the public page
    never pretends an untracked link earns a commission.
    """
    imported, errors, products = 0, [], []
    for index, raw in enumerate(str(text or "").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINK_RE.search(line)
        if not match:
            errors.append({"line": index, "error": "No http(s) link found"})
            continue
        url = match.group(0).rstrip(").,;")
        fields = [part.strip() for part in line.split("|")]
        url_field = next((i for i, part in enumerate(fields) if _LINK_RE.search(part)), -1)
        before = [part for part in fields[:url_field] if part] if url_field > 0 else []
        after = [part for part in fields[url_field + 1:] if part] if url_field >= 0 else []
        title = before[0] if before else _humanise_url(url)
        try:
            external = urlparse(url).path.rstrip("/").split("/")[-1][:120] or None
            tracked = bool(real or _looks_real_affiliate(url))
            data = {
                "external_id": external,
                "title": title,
                "title_ta": "",
                "category": (after[2] if len(after) > 2 and after[2] else category) or "General",
                "price": after[0] if len(after) > 0 else 0,
                "mrp": after[1] if len(after) > 1 else 0,
                "commission_percent": after[3] if len(after) > 3 else 0,
                "affiliate_url": url,
                "image_url": after[4] if len(after) > 4 else "",
                "features": [],
                "cautions": [],
                "demo": not tracked,
                "affiliate_verified": bool(real),
                "active": True,
            }
            product = finds.upsert_product(data, source="link-import")
            imported += 1
            products.append({"id": product.get("id"), "title": product.get("title"),
                             "demo": product.get("demo"),
                             "network": affiliate.detect_network(url),
                             "network_label": affiliate.network_label(affiliate.detect_network(url))})
        except Exception as exc:
            errors.append({"line": index, "error": f"{type(exc).__name__}: {exc}"})
    return {"imported": imported, "errors": errors[:50], "error_count": len(errors),
            "products": products}


# ---------------------------------------------------------------------------
# Hands-off catalogue feed
# ---------------------------------------------------------------------------
def _feed_dir() -> Path:
    path = _finds_dir() / "feed"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _feed_state_path() -> Path:
    return _finds_dir() / "feed_state.json"


def _read_feed_state() -> dict:
    try:
        data = json.loads(_feed_state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_feed_state(state: dict) -> None:
    try:
        _feed_state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Feed state unwritable: %s", exc)


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TamilBudgetFinds-Autopilot/1.0",
                 "Accept": "text/csv,text/plain,application/csv,*/*;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Feed is larger than 5 MB")
    return raw.decode("utf-8-sig", errors="replace")


def _looks_like_csv(text: str) -> bool:
    first = next((line for line in str(text or "").splitlines() if line.strip()), "")
    if not first:
        return False
    lower = first.lower()
    if first.lstrip().startswith(("http://", "https://", "{")):
        return False
    return "," in first and any(token in lower for token in
                                ("title", "product", "url", "link", "price", "affiliate", "sku"))


def _import_feed_text(text: str) -> dict:
    body = str(text or "").strip()
    if not body:
        return {"imported": 0, "errors": [{"line": 0, "error": "Feed is empty"}],
                "error_count": 1, "kind": "empty"}
    if body[:1] == "<":
        return {"imported": 0,
                "errors": [{"line": 0, "error": "Feed returned HTML, not CSV. Publish the sheet as CSV."}],
                "error_count": 1, "kind": "html"}
    if _looks_like_csv(body):
        result = finds.import_products(body)
        result["kind"] = "csv"
        return result
    result = import_links(body, real=False)
    result["kind"] = "links"
    return result


def _read_feed_files(path: Path) -> list[tuple[str, str]]:
    files = [path] if path.is_file() else sorted(
        [p for p in path.iterdir()
         if p.is_file() and p.suffix.lower() in {".csv", ".txt", ".tsv"}],
        key=lambda p: p.stat().st_mtime,
    )
    output = []
    for item in files[:50]:
        try:
            if item.stat().st_size > 5_000_000:
                output.append((str(item), ""))
                continue
            output.append((str(item), item.read_text(encoding="utf-8-sig", errors="replace")))
        except OSError as exc:
            output.append((str(item), f"__ERROR__{exc}"))
    return output


def sync_feed(force: bool = False) -> dict:
    """Import a CSV/URL feed so the catalogue refills without a human click.

    The owner configures one URL (a published Google Sheet, an affiliate
    network export, or a small static CSV) or drops files into
    ``storage/finds/feed``. The importer is idempotent: identical content is
    skipped, and products are upserted by external id.
    """
    cfg = load_config()
    url = str(cfg.get("feed_url") or "").strip()
    raw_path = str(cfg.get("feed_path") or "").strip()
    path = Path(raw_path) if raw_path else _feed_dir()
    if not url and not raw_path and not any(_feed_dir().iterdir()):
        return {"configured": False, "at": now_ist().isoformat(timespec="seconds"),
                "imported": 0, "errors": [], "sources": [], "skipped": True,
                "detail": "No feed URL and the feed folder is empty."}
    if not url and not path.exists():
        return {"configured": True, "at": now_ist().isoformat(timespec="seconds"),
                "imported": 0, "errors": [{"source": str(path), "error": "Feed path not found"}],
                "sources": [], "skipped": False}

    state = _read_feed_state()
    sources_state = state.get("sources") if isinstance(state.get("sources"), dict) else {}
    results, errors, imported = [], [], 0

    pending: list[tuple[str, str]] = []
    if url:
        pending.append((url, "url"))
    if raw_path or _feed_dir().is_dir():
        for name, text in _read_feed_files(path):
            pending.append((name, "file" if text != "" else "error"))

    for name, kind in pending:
        if kind == "error" or not name:
            errors.append({"source": name, "error": "Could not read the file"})
            continue
        try:
            if name == url and kind == "url":
                text = _fetch_text(name)
            else:
                text = next((t for n, t in _read_feed_files(path) if n == name), "")
            digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
            previous = sources_state.get(name) if isinstance(sources_state.get(name), dict) else {}
            if not force and previous.get("hash") == digest:
                results.append({"source": name, "skipped": "unchanged", "imported": 0})
                continue
            result = _import_feed_text(text)
            imported += int(result.get("imported") or 0)
            errors.extend([{"source": name, **item} for item in (result.get("errors") or [])][:10])
            sources_state[name] = {
                "hash": digest,
                "at": now_ist().isoformat(timespec="seconds"),
                "imported": int(result.get("imported") or 0),
                "kind": result.get("kind"),
            }
            results.append({"source": name, "imported": int(result.get("imported") or 0),
                            "kind": result.get("kind")})
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            errors.append({"source": name, "error": f"{type(exc).__name__}: {exc}"})
            results.append({"source": name, "imported": 0, "error": str(exc)[:300]})

    state.update({
        "last_sync": now_ist().isoformat(timespec="seconds"),
        "last_imported": imported,
        "last_error": errors[0].get("error") if errors else "",
        "sources": sources_state,
    })
    _write_feed_state(state)
    return {"configured": True, "at": state["last_sync"], "imported": imported,
            "errors": errors[:50], "error_count": len(errors), "sources": results,
            "skipped": False}


def feed_status() -> dict:
    cfg = load_config()
    state = _read_feed_state()
    url = str(cfg.get("feed_url") or "").strip()
    raw_path = str(cfg.get("feed_path") or "").strip()
    inbox = _feed_dir()
    files = sorted([p.name for p in inbox.iterdir() if p.is_file()]) if inbox.is_dir() else []
    return {
        "configured": bool(url or raw_path or files),
        "url": url,
        "path": raw_path or str(inbox),
        "inbox": str(inbox),
        "inbox_files": files[:20],
        "last_sync": state.get("last_sync") or "",
        "last_imported": int(state.get("last_imported") or 0),
        "last_error": state.get("last_error") or "",
        "sources": list((state.get("sources") or {}).keys())[:20],
    }


# ---------------------------------------------------------------------------
# Status payload for the dashboard / API
# ---------------------------------------------------------------------------
def _platform_rows(run: dict | None, job: dict | None, schedule: dict) -> list[dict]:
    posted = _posted_platforms(job.get("id") if job else None)
    rows = []
    for platform in PLATFORMS:
        stage = (run or {}).get("stages", {}).get(platform, {})
        rows.append({
            "platform": platform,
            "label": PLATFORM_LABEL[platform],
            "posted": posted.get(platform, False),
            "stage_status": stage.get("status", "pending"),
            "stage_detail": stage.get("detail", ""),
            "run_time": schedule.get(platform, {}).get("run_time", DEFAULT_TIMES[platform]),
            "enabled": bool(schedule.get(platform, {}).get("enabled")),
        })
    return rows


def status(day: str | None = None) -> dict:
    day = _parse_day(day)
    cfg = load_config()
    run = get_run(day)
    if run:
        run = reconcile(day, run)
    job = _job_for_day(day)
    schedule = schedule_map()
    product = finds.get_product(run["product_id"]) if run and run.get("product_id") else best_product(day)
    pinned = finds.pinned_product(day)
    metrics = _metrics(product["id"] if product else None, day)
    mon = monetization(product)
    platforms = _platform_rows(run, job, schedule)
    readiness = []
    for item in sorted(finds.list_products(active_only=True, limit=1000),
                       key=lambda p: candidate_score(p, day), reverse=True)[:10]:
        ready = monetization(item)
        readiness.append({
            "id": item["id"], "title": item.get("title_ta") or item.get("title"),
            "title_en": item.get("title"), "category": item.get("category"),
            "price": item.get("price"), "score": item.get("score"),
            "candidate_score": candidate_score(item, day),
            "demo": item.get("demo"), "monetization_ready": ready["ready"],
            "issues": ready["issues"],
        })

    blockers = []
    is_today = day == today()
    feed = feed_status()
    if not product:
        blockers.append("No active products. Connect a feed or import the affiliate CSV.")
    if feed.get("last_error"):
        blockers.append(f"Feed error: {feed['last_error']}")
    if cfg.get("auto_mode") and not feed.get("configured"):
        blockers.append("Zero-touch mode has no product feed yet. Add a feed URL or drop a CSV into the feed folder.")
    if job and job.get("status") == "failed":
        blockers.append(f"Video job failed: {job.get('message') or 'unknown error'}")
    if product and mon["issues"] and cfg.get("require_affiliate_link"):
        blockers.append("Publishing is blocked until a real affiliate link is added.")
    if is_today and job and job.get("status") == "complete":
        now = now_ist()
        for platform in platforms:
            if not platform["posted"] and platform["enabled"] and now >= _due_at(day, platform["run_time"]):
                blockers.append(f"{platform['label']} is due but not posted yet.")
    if run and run.get("status") == "awaiting_approval":
        blockers.append("The product is waiting for owner approval.")

    return {
        "day": day,
        "at": now_ist().isoformat(timespec="seconds"),
        "config": cfg,
        "run": run,
        "product": _public_product(product, day),
        "pinned": _public_product(pinned, day),
        "monetization": mon,
        "metrics": metrics,
        "job": {
            "id": job.get("id") if job else None,
            "status": job.get("status") if job else None,
            "message": job.get("message") if job else None,
            "auto_render": job.get("auto_render") if job else None,
        },
        "schedule": schedule,
        "platforms": platforms,
        "blockers": blockers,
        "recommendations": recommendations(day, limit=5),
        "readiness": readiness,
        "feed": feed_status(),
        "recent_runs": list_runs(limit=14),
        "events": list_events(run["id"] if run else None, limit=20),
        "scope": "Zero-touch: feed -> select -> render -> post. The existing 19:00/19:30/19:45/20:00 "
                 "schedules remain the executor and the Autopilot retries only missing platforms. "
                 "No fake clicks, orders or engagement.",
    }
