"""Tamil Budget Finds — Meesho affiliate catalogue, clicks and orders.

This module deliberately uses its own SQLite file (the same pattern as
``app.store``, ``app.video_creator.jobs`` and ``app.video_creator.schedules``)
so the affiliate business can be tested without changing the main application
schema or risking the existing educational channels.

Everything the public page, admin page, video script and daily scheduler need is
here: CSV import, product scoring, deterministic daily rotation, click tracking,
order/commission import and a small analytics summary.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from app import affiliate
from app.config.settings import settings

FINDS_DIR = Path(settings.STORAGE_PATH) / "finds"
DB = FINDS_DIR / "finds.sqlite3"
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# Link-preview crawlers and CLI probes are not shoppers. Without this filter a
# single Facebook/Instagram share can add several "clicks" before a human taps.
_BOT_UA_RE = re.compile(
    r"(bot|crawler|spider|facebookexternalhit|preview|curl/|wget/|python-requests|httpclient|headlesschrome)",
    re.IGNORECASE,
)

PRODUCT_COLUMNS = (
    "id", "external_id", "title", "title_ta", "category", "price", "mrp",
    "rating", "orders_count", "return_risk", "commission_percent",
    "commission_amount", "affiliate_url", "image_url", "features", "cautions",
    "score", "active", "demo", "affiliate_verified", "source", "last_used_at",
    "use_count", "created_at", "updated_at",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    FINDS_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    _ensure_schema(db)
    return db


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            external_id TEXT UNIQUE,
            title TEXT NOT NULL,
            title_ta TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'General',
            price REAL NOT NULL DEFAULT 0,
            mrp REAL NOT NULL DEFAULT 0,
            rating REAL NOT NULL DEFAULT 0,
            orders_count INTEGER NOT NULL DEFAULT 0,
            return_risk TEXT NOT NULL DEFAULT 'low',
            commission_percent REAL NOT NULL DEFAULT 0,
            commission_amount REAL NOT NULL DEFAULT 0,
            affiliate_url TEXT NOT NULL,
            image_url TEXT NOT NULL DEFAULT '',
            features TEXT NOT NULL DEFAULT '[]',
            cautions TEXT NOT NULL DEFAULT '[]',
            score REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            demo INTEGER NOT NULL DEFAULT 0,
            affiliate_verified INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            last_used_at TEXT,
            use_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clicks (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'direct',
            referrer TEXT NOT NULL DEFAULT '',
            user_agent TEXT NOT NULL DEFAULT '',
            ip TEXT NOT NULL DEFAULT '',
            clicked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            product_id TEXT,
            platform TEXT NOT NULL DEFAULT 'meesho',
            sale_amount REAL NOT NULL DEFAULT 0,
            commission REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            ordered_at TEXT,
            raw TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS day_picks (
            day TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_finds_clicks_product ON clicks(product_id, clicked_at);
        CREATE INDEX IF NOT EXISTS ix_finds_orders_product ON orders(product_id, ordered_at);
        CREATE INDEX IF NOT EXISTS ix_finds_products_active ON products(active, score);
        """
    )
    # Existing databases predate the multi-network catalogue. Adding the column
    # in place keeps the same SQLite file and all click/order history intact.
    columns = {row[1] for row in db.execute("PRAGMA table_info(products)").fetchall()}
    if "affiliate_verified" not in columns:
        db.execute("ALTER TABLE products ADD COLUMN affiliate_verified INTEGER NOT NULL DEFAULT 0")
        db.commit()


def _json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else default
    except (TypeError, ValueError):
        return default


def _clean_text(value, limit=500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _num(value, default=0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().lower()
    if not text:
        return float(default)
    text = (text.replace("₹", "").replace("rs.", "").replace("rs", "")
            .replace(",", "").replace("%", "").strip())
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return float(default)
    try:
        return float(match.group(0))
    except ValueError:
        return float(default)


def _int(value, default=0) -> int:
    return int(round(_num(value, default)))


def _truth(value, default=True) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", "inactive", "disabled"}


def _list(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        text = str(value or "").strip()
        if not text:
            return []
        if "|" in text:
            items = text.split("|")
        elif "\n" in text:
            items = text.splitlines()
        elif ";" in text:
            items = text.split(";")
        elif "," in text:
            items = text.split(",")
        else:
            items = [text]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = _clean_text(item, 220)
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            out.append(clean)
    return out[:10]


def _safe_url(value) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Affiliate URL must be a public http(s) link")
    return url[:2000]


def _product_id(external_id: str | None, requested: str | None = None) -> str:
    if requested:
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "", requested)[:40]
        if cleaned:
            return cleaned
    if external_id:
        digest = uuid.uuid5(uuid.NAMESPACE_URL, "meesho:" + external_id).hex[:12]
        return "M" + digest.upper()
    return "M" + uuid.uuid4().hex[:12].upper()


def score_product(data: dict) -> float:
    """A transparent 0-100 buying-guide score (not a promise of quality)."""
    price = max(0.0, _num(data.get("price")))
    mrp = max(0.0, _num(data.get("mrp")))
    rating = max(0.0, min(5.0, _num(data.get("rating"))))
    orders = max(0, _int(data.get("orders_count")))
    commission = max(0.0, _num(data.get("commission_percent")))
    risk = str(data.get("return_risk") or "low").strip().lower()

    discount = ((mrp - price) / mrp * 100.0) if mrp > price > 0 else 0.0
    value = min(28.0, max(0.0, discount) * 0.42)
    trust = max(0.0, (rating - 3.2) * 12.0)
    demand = min(18.0, math.log10(orders + 1) * 4.2)
    payout = min(12.0, commission * 0.8)
    band = 8.0 if 199 <= price <= 799 else 5.0 if price <= 1499 else 2.0 if price <= 2999 else 0.0
    penalty = {"high": 14.0, "medium": 5.0}.get(risk, 0.0)
    return round(max(0.0, min(100.0, value + trust + demand + payout + band - penalty)), 2)


def _row_product(row: sqlite3.Row | dict, clicks=0, orders=0, commission=0.0, public=False) -> dict:
    data = dict(row)
    data["features"] = _json(data.get("features"), [])
    data["cautions"] = _json(data.get("cautions"), [])
    data["price"] = round(_num(data.get("price")), 2)
    data["mrp"] = round(_num(data.get("mrp")), 2)
    data["rating"] = round(_num(data.get("rating")), 2)
    data["orders_count"] = _int(data.get("orders_count"))
    data["commission_percent"] = round(_num(data.get("commission_percent")), 2)
    data["commission_amount"] = round(_num(data.get("commission_amount")), 2)
    data["score"] = round(_num(data.get("score")), 2)
    data["active"] = bool(data.get("active"))
    data["demo"] = bool(data.get("demo"))
    data["affiliate_verified"] = bool(data.get("affiliate_verified"))
    data["use_count"] = _int(data.get("use_count"))
    data["clicks"] = _int(clicks)
    data["orders"] = _int(orders)
    data["commission_earned"] = round(_num(commission), 2)
    data["discount_percent"] = (round((data["mrp"] - data["price"]) / data["mrp"] * 100)
                                if data["mrp"] > data["price"] > 0 else 0)
    data["buy_url"] = f"/go/{data['id']}"
    if public:
        for key in ("affiliate_url", "external_id", "source", "last_used_at",
                    "return_risk", "commission_percent", "commission_amount",
                    "use_count", "created_at", "updated_at"):
            data.pop(key, None)
    return data


def _aggregates(db: sqlite3.Connection) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in db.execute("SELECT product_id, COUNT(*) AS n FROM clicks GROUP BY product_id"):
        out.setdefault(row["product_id"], {})["clicks"] = row["n"]
    for row in db.execute(
            "SELECT product_id, COUNT(*) AS n, COALESCE(SUM(commission), 0) AS c "
            "FROM orders GROUP BY product_id"):
        out.setdefault(row["product_id"], {}).update(orders=row["n"], commission=row["c"])
    return out


def get_product(product_id: str, public: bool = False) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM products WHERE id=?", (str(product_id),)).fetchone()
        if not row:
            return None
        agg = _aggregates(db).get(str(product_id), {})
    return _row_product(row, agg.get("clicks", 0), agg.get("orders", 0),
                        agg.get("commission", 0), public=public)


def list_products(active_only: bool = False, category: str | None = None,
                  search: str | None = None, public: bool = False, limit: int = 250) -> list[dict]:
    clauses, params = [], []
    if active_only:
        clauses.append("active=1")
    if category and category.strip():
        clauses.append("lower(category)=lower(?)")
        params.append(category.strip())
    if search and search.strip():
        clauses.append("(lower(title) LIKE ? OR lower(title_ta) LIKE ? OR lower(category) LIKE ?)")
        needle = f"%{search.strip().lower()}%"
        params.extend([needle, needle, needle])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(int(limit), 1000)))
    with _connect() as db:
        rows = db.execute(f"SELECT * FROM products{where} ORDER BY score DESC, orders_count DESC, created_at DESC LIMIT ?",
                          params).fetchall()
        aggs = _aggregates(db)
    return [_row_product(row, aggs.get(row["id"], {}).get("clicks", 0),
                         aggs.get(row["id"], {}).get("orders", 0),
                         aggs.get(row["id"], {}).get("commission", 0), public=public)
            for row in rows]


def categories() -> list[str]:
    with _connect() as db:
        return [row[0] for row in db.execute(
            "SELECT DISTINCT category FROM products WHERE active=1 AND category<>'' ORDER BY category")]


def delete_product(product_id: str) -> bool:
    with _connect() as db:
        deleted = db.execute("DELETE FROM products WHERE id=?", (str(product_id),)).rowcount
        db.commit()
    return bool(deleted)


def list_orders(limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    with _connect() as db:
        rows = db.execute(
            "SELECT o.*, p.title AS product_title FROM orders o "
            "LEFT JOIN products p ON p.id=o.product_id "
            "ORDER BY COALESCE(o.ordered_at, o.created_at) DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def upsert_product(data: dict, source: str = "manual") -> dict:
    title = _clean_text(data.get("title") or data.get("name") or data.get("product_name"), 500)
    if not title:
        raise ValueError("Product title is required")
    affiliate_url = _safe_url(data.get("affiliate_url") or data.get("url") or data.get("link"))
    external_id = _clean_text(data.get("external_id") or data.get("product_id") or
                              data.get("meesho_id"), 120) or None
    requested = _clean_text(data.get("id"), 60) or None
    price = max(0.0, _num(data.get("price") or data.get("sale_price")))
    mrp = max(price, _num(data.get("mrp") or data.get("original_price")))
    features = _list(data.get("features"))
    cautions = _list(data.get("cautions") or data.get("warnings"))
    now = _now()

    with _connect() as db:
        existing = None
        if external_id:
            existing = db.execute("SELECT * FROM products WHERE external_id=?", (external_id,)).fetchone()
        if not existing and requested:
            existing = db.execute("SELECT * FROM products WHERE id=?", (requested,)).fetchone()
        product_id = existing["id"] if existing else _product_id(external_id, requested)
        created = existing["created_at"] if existing else now
        last_used = existing["last_used_at"] if existing else None
        use_count = existing["use_count"] if existing else 0
        active = _truth(data.get("active"), bool(existing["active"]) if existing else True)
        verified = _truth(
            data.get("affiliate_verified", data.get("real")),
            bool(existing["affiliate_verified"]) if existing else False,
        )
        tracked = affiliate.is_affiliate_link(affiliate_url, verified=verified)
        explicit_demo = data.get("demo")
        demo = (_truth(explicit_demo, not tracked)
                if explicit_demo is not None and explicit_demo != "" else not tracked)
        risk = _clean_text(data.get("return_risk") or (existing["return_risk"] if existing else "low"), 20).lower()
        if risk not in {"low", "medium", "high"}:
            risk = "low"
        record = {
            "id": product_id,
            "external_id": external_id,
            "title": title,
            "title_ta": _clean_text(data.get("title_ta") or data.get("tamil_title") or
                                    (existing["title_ta"] if existing else ""), 500),
            "category": _clean_text(data.get("category") or (existing["category"] if existing else "General"), 100) or "General",
            "price": price,
            "mrp": mrp,
            "rating": max(0.0, min(5.0, _num(data.get("rating"), existing["rating"] if existing else 0))),
            "orders_count": max(0, _int(data.get("orders_count") or data.get("orders"), existing["orders_count"] if existing else 0)),
            "return_risk": risk,
            "commission_percent": max(0.0, _num(data.get("commission_percent") or data.get("commission"), existing["commission_percent"] if existing else 0)),
            "commission_amount": max(0.0, _num(data.get("commission_amount"), existing["commission_amount"] if existing else 0)),
            "affiliate_url": affiliate_url,
            "image_url": str(data.get("image_url") or data.get("image") or (existing["image_url"] if existing else "")).strip()[:200_000],
            "features": json.dumps(features, ensure_ascii=False),
            "cautions": json.dumps(cautions, ensure_ascii=False),
            "active": 1 if active else 0,
            "demo": 1 if demo else 0,
            "affiliate_verified": 1 if verified else 0,
            "source": _clean_text(source or (existing["source"] if existing else "manual"), 50) or "manual",
            "last_used_at": last_used,
            "use_count": use_count,
            "created_at": created,
            "updated_at": now,
        }
        record["score"] = score_product(record)
        columns = ", ".join(PRODUCT_COLUMNS)
        placeholders = ", ".join("?" for _ in PRODUCT_COLUMNS)
        db.execute(f"INSERT OR REPLACE INTO products ({columns}) VALUES ({placeholders})",
                   tuple(record[c] for c in PRODUCT_COLUMNS))
    return get_product(product_id) or {}


def today_pick(day: date | None = None) -> dict | None:
    """Pick one active product for a day, reusing the same choice on retries."""
    day = day or datetime.now(IST).date()
    day_iso = day.isoformat()
    now = _now()
    recent_cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            # The Autopilot pins a product for the day before the 19:00 render.
            # Honouring that pin here is what lets the agent actually choose the
            # product while the existing scheduler remains the executor.
            pinned = db.execute(
                "SELECT product_id FROM day_picks WHERE day=?", (day_iso,)).fetchone()
            if pinned:
                chosen = db.execute(
                    "SELECT * FROM products WHERE id=? AND active=1",
                    (pinned["product_id"],)).fetchone()
                if chosen:
                    # Count the use once, not on every status/retry read.
                    if (chosen["last_used_at"] or "")[:10] != day_iso:
                        db.execute(
                            "UPDATE products SET last_used_at=?, use_count=use_count+1, updated_at=? "
                            "WHERE id=?", (now, now, chosen["id"]))
                        db.commit()
                        chosen = db.execute(
                            "SELECT * FROM products WHERE id=?", (chosen["id"],)).fetchone()
                    else:
                        db.commit()
                    agg = _aggregates(db).get(chosen["id"], {})
                    return _row_product(chosen, agg.get("clicks", 0), agg.get("orders", 0),
                                        agg.get("commission", 0))
                # Pinned product was hidden/deleted: fall through to normal rotation.
                db.execute("DELETE FROM day_picks WHERE day=?", (day_iso,))
            existing = db.execute(
                "SELECT * FROM products WHERE active=1 AND substr(last_used_at, 1, 10)=? "
                "ORDER BY score DESC LIMIT 1", (day_iso,)).fetchone()
            if existing:
                db.commit()
                agg = _aggregates(db).get(existing["id"], {})
                return _row_product(existing, agg.get("clicks", 0), agg.get("orders", 0),
                                    agg.get("commission", 0))
            rows = db.execute(
                "SELECT * FROM products WHERE active=1 ORDER BY score DESC, orders_count DESC, price ASC").fetchall()
            if not rows:
                db.commit()
                return None
            fresh = [row for row in rows if not row["last_used_at"] or row["last_used_at"] < recent_cutoff]
            chosen = (fresh or rows)[0]
            db.execute("UPDATE products SET last_used_at=?, use_count=use_count+1, updated_at=? WHERE id=?",
                       (now, now, chosen["id"]))
            db.commit()
            refreshed = db.execute("SELECT * FROM products WHERE id=?", (chosen["id"],)).fetchone()
            agg = _aggregates(db).get(chosen["id"], {})
        except Exception:
            db.rollback()
            raise
    return _row_product(refreshed, agg.get("clicks", 0), agg.get("orders", 0),
                        agg.get("commission", 0))


def pin_product(day: date | str | None, product_id: str, reason: str = "") -> dict:
    """Pin one active product to a calendar day before the daily render.

    The Autopilot calls this at 18:00 IST; ``today_pick`` then returns the pinned
    product at 19:00, so selection and rendering stay decoupled and retry-safe.
    """
    day_iso = day.isoformat() if isinstance(day, date) else (str(day or "")[:10] or
                                                            datetime.now(IST).date().isoformat())
    with _connect() as db:
        row = db.execute("SELECT id FROM products WHERE id=? AND active=1",
                         (str(product_id),)).fetchone()
        if not row:
            raise ValueError("Product not found or inactive")
        db.execute(
            "INSERT INTO day_picks (day, product_id, reason, created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET product_id=excluded.product_id, "
            "reason=excluded.reason, created_at=excluded.created_at",
            (day_iso, str(product_id), _clean_text(reason, 300), _now()))
        db.commit()
    return get_product(product_id) or {}


def unpin_product(day: date | str | None = None) -> bool:
    day_iso = day.isoformat() if isinstance(day, date) else (str(day or "")[:10] or
                                                            datetime.now(IST).date().isoformat())
    with _connect() as db:
        removed = db.execute("DELETE FROM day_picks WHERE day=?", (day_iso,)).rowcount
        db.commit()
    return bool(removed)


def pinned_product(day: date | str | None = None) -> dict | None:
    day_iso = day.isoformat() if isinstance(day, date) else (str(day or "")[:10] or
                                                            datetime.now(IST).date().isoformat())
    with _connect() as db:
        row = db.execute("SELECT product_id FROM day_picks WHERE day=?", (day_iso,)).fetchone()
    return get_product(row["product_id"]) if row else None


def record_click(product_id: str, platform: str = "direct", referrer: str = "",
                 user_agent: str = "", ip: str = "") -> dict | None:
    platform = re.sub(r"[^a-z0-9_-]", "", (platform or "direct").lower())[:30] or "direct"
    bot = bool(_BOT_UA_RE.search(str(user_agent or "")))
    with _connect() as db:
        row = db.execute("SELECT * FROM products WHERE id=? AND active=1", (str(product_id),)).fetchone()
        if not row:
            return None
        if bot:
            # Link-preview crawlers still need the redirect so Facebook,
            # WhatsApp, etc. can build a preview, but they must not inflate
            # the shopper click count.
            return _row_product(row)
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                "INSERT INTO clicks (id, product_id, platform, referrer, user_agent, ip, clicked_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, str(product_id), platform, str(referrer or "")[:1000],
                 str(user_agent or "")[:1000], str(ip or "")[:80], _now()))
            db.commit()
            data = _row_product(row)
        except Exception:
            db.rollback()
            raise
    return data


def _normalise_row(row: dict) -> dict:
    return {
        re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_"): ("" if value is None else str(value).strip())
        for key, value in row.items()
    }


def _pick(row: dict, *names: str, default=""):
    for name in names:
        if name in row and row[name] != "":
            return row[name]
    return default


def import_products(csv_text: str) -> dict:
    text = (csv_text or "").lstrip("\ufeff")
    if not text.strip():
        raise ValueError("CSV is empty")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV needs a header row")
    imported, errors = 0, []
    for line_no, raw in enumerate(reader, start=2):
        row = _normalise_row(raw)
        try:
            data = {
                "external_id": _pick(row, "external_id", "product_id", "meesho_id", "sku"),
                "title": _pick(row, "title", "product_name", "name"),
                "title_ta": _pick(row, "title_ta", "tamil_title", "tamil_name"),
                "category": _pick(row, "category", "sub_category", default="General"),
                "price": _pick(row, "price", "sale_price", "offer_price", "selling_price"),
                "mrp": _pick(row, "mrp", "original_price", "list_price"),
                "rating": _pick(row, "rating", "product_rating", "stars"),
                "orders_count": _pick(row, "orders_count", "orders", "order_count", "units_sold"),
                "return_risk": _pick(row, "return_risk", "risk", default="low"),
                "commission_percent": _pick(row, "commission_percent", "commission_rate", "commission"),
                "affiliate_url": _pick(row, "affiliate_url", "affiliate_link", "url", "link"),
                "image_url": _pick(row, "image_url", "image", "image_link", "photo"),
                "features": _pick(row, "features", "benefits", "highlights"),
                "cautions": _pick(row, "cautions", "warnings", "watchouts"),
                "active": _pick(row, "active", default="true"),
                # Do not default a plain product URL to "real": the catalogue
                # infers demo/affiliate state from the link itself.
                "demo": _pick(row, "demo"),
                "affiliate_verified": _pick(row, "affiliate_verified", "real"),
            }
            upsert_product(data, source="csv")
            imported += 1
        except ValueError as exc:
            errors.append({"line": line_no, "error": str(exc)})
        except Exception as exc:  # keep importing the remaining rows
            errors.append({"line": line_no, "error": f"{type(exc).__name__}: {exc}"})
    return {"imported": imported, "errors": errors[:50], "error_count": len(errors)}


def import_orders(csv_text: str) -> dict:
    text = (csv_text or "").lstrip("\ufeff")
    if not text.strip():
        raise ValueError("CSV is empty")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV needs a header row")
    imported, errors = 0, []
    with _connect() as db:
        for line_no, raw in enumerate(reader, start=2):
            row = _normalise_row(raw)
            try:
                order_id = _pick(row, "order_id", "order", "sub_order_id", "id")
                if not order_id:
                    raise ValueError("order_id is required")
                product_key = _pick(row, "product_id", "external_id", "sku", "product")
                product = None
                if product_key:
                    product = db.execute("SELECT id FROM products WHERE id=? OR external_id=?",
                                         (product_key, product_key)).fetchone()
                sale = max(0.0, _num(_pick(row, "sale_amount", "amount", "order_amount", "price")))
                commission = max(0.0, _num(_pick(row, "commission", "commission_amount", "earnings")))
                ordered_at = _pick(row, "ordered_at", "order_date", "date", "created_at") or _now()
                status = _clean_text(_pick(row, "status", "order_status", default="pending"), 40) or "pending"
                db.execute(
                    "INSERT INTO orders (id, order_id, product_id, platform, sale_amount, commission, status, ordered_at, raw, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET "
                    "product_id=excluded.product_id, platform=excluded.platform, sale_amount=excluded.sale_amount, "
                    "commission=excluded.commission, status=excluded.status, ordered_at=excluded.ordered_at, raw=excluded.raw",
                    (uuid.uuid4().hex, order_id, product["id"] if product else None,
                     _clean_text(_pick(row, "platform", default="meesho"), 30) or "meesho",
                     sale, commission, status, ordered_at[:40],
                     json.dumps(raw, ensure_ascii=False)[:20_000], _now()))
                imported += 1
            except Exception as exc:
                errors.append({"line": line_no, "error": str(exc)})
        db.commit()
    return {"imported": imported, "errors": errors[:50], "error_count": len(errors)}


def _day_ist(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(IST).date().isoformat()
    except ValueError:
        return str(iso)[:10]


def analytics(days: int = 30) -> dict:
    days = max(1, min(int(days), 365))
    now = datetime.now(UTC)
    since = (now - timedelta(days=days)).isoformat()
    since7 = (now - timedelta(days=7)).isoformat()
    with _connect() as db:
        products = db.execute("SELECT * FROM products").fetchall()
        clicks_total = db.execute("SELECT COUNT(*) FROM clicks").fetchone()[0]
        clicks_7 = db.execute("SELECT COUNT(*) FROM clicks WHERE clicked_at>=?", (since7,)).fetchone()[0]
        clicks_period = db.execute("SELECT COUNT(*) FROM clicks WHERE clicked_at>=?", (since,)).fetchone()[0]
        by_platform = [dict(row) for row in db.execute(
            "SELECT platform, COUNT(*) AS clicks FROM clicks WHERE clicked_at>=? GROUP BY platform ORDER BY clicks DESC",
            (since,))]
        orders = db.execute("SELECT * FROM orders WHERE COALESCE(ordered_at, created_at)>=?", (since,)).fetchall()
        orders_total = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        all_sales = db.execute("SELECT COALESCE(SUM(sale_amount),0), COALESCE(SUM(commission),0) FROM orders").fetchone()
        sales = sum(_num(row["sale_amount"]) for row in orders)
        commission = sum(_num(row["commission"]) for row in orders)
        statuses: dict[str, int] = {}
        for row in orders:
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        product_map = {row["id"]: row for row in products}
        click_map: dict[str, int] = {}
        for row in db.execute("SELECT product_id, COUNT(*) AS n FROM clicks WHERE clicked_at>=? GROUP BY product_id", (since,)):
            click_map[row["product_id"]] = row["n"]
        order_map: dict[str, dict] = {}
        for row in orders:
            if row["product_id"]:
                item = order_map.setdefault(row["product_id"], {"orders": 0, "commission": 0.0})
                item["orders"] += 1
                item["commission"] += _num(row["commission"])
        top = []
        for pid, values in order_map.items():
            product = product_map.get(pid)
            if product:
                top.append({"id": pid, "title": product["title"], "orders": values["orders"],
                            "commission": round(values["commission"], 2),
                            "clicks": click_map.get(pid, 0)})
        top.sort(key=lambda item: (item["orders"], item["commission"]), reverse=True)
        daily = []
        start = (now - timedelta(days=13)).astimezone(IST).date()
        for offset in range(14):
            current = start + timedelta(days=offset)
            daily.append({"date": current.isoformat(), "clicks": 0, "orders": 0, "commission": 0.0})
        daily_map = {item["date"]: item for item in daily}
        for row in db.execute("SELECT clicked_at FROM clicks WHERE clicked_at>=?", (since,)):
            item = daily_map.get(_day_ist(row["clicked_at"]))
            if item:
                item["clicks"] += 1
        for row in orders:
            item = daily_map.get(_day_ist(row["ordered_at"] or row["created_at"]))
            if item:
                item["orders"] += 1
                item["commission"] = round(item["commission"] + _num(row["commission"]), 2)
    return {
        "products": len(products),
        "active_products": sum(1 for row in products if row["active"]),
        "clicks": clicks_total,
        "clicks_7d": clicks_7,
        "clicks_period": clicks_period,
        "clicks_by_platform": by_platform,
        "orders": orders_total,
        "orders_period": len(orders),
        "sales": round(sales, 2),
        "sales_all": round(_num(all_sales[0]), 2),
        "commission": round(commission, 2),
        "commission_all": round(_num(all_sales[1]), 2),
        "conversion_percent": round(len(orders) / clicks_period * 100, 2) if clicks_period else 0,
        "statuses": statuses,
        "top_products": top[:8],
        "daily": daily,
        "period_days": days,
    }


def _demo_image(label: str, start: str, end: str) -> str:
    """Small offline product card used only by the seeded demo catalogue."""
    from PIL import Image, ImageDraw, ImageFont

    def rgb(value):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    top, bottom = rgb(start), rgb(end)
    image = Image.new("RGB", (800, 800), top)
    draw = ImageDraw.Draw(image)
    for y in range(800):
        ratio = y / 799
        draw.line([(0, y), (800, y)], fill=tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3)))
    overlay = Image.new("RGBA", (800, 800), (255, 255, 255, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((54, 54, 746, 746), radius=40, fill=(255, 255, 255, 34), outline=(255, 255, 255, 90), width=3)
    od.ellipse((110, 150, 690, 650), fill=(255, 255, 255, 20))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_path = next((path for path in (
        r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\calibrib.ttf") if Path(path).is_file()), None)
    try:
        big = ImageFont.truetype(font_path, 96) if font_path else ImageFont.load_default()
        small = ImageFont.truetype(font_path, 34) if font_path else ImageFont.load_default()
    except OSError:
        big = small = ImageFont.load_default()
    for text, font, y in (("TAMIL BUDGET FINDS", small, 82), (label, big, 360)):
        box = draw.textbbox((0, 0), text, font=font)
        width = box[2] - box[0]
        draw.text(((800 - width) / 2, y), text, font=font, fill=(255, 255, 255), stroke_width=2,
                  stroke_fill=(0, 0, 0))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def seed_demo() -> dict:
    """Idempotent demo catalogue; safe to run repeatedly."""
    products = [
        {
            "external_id": "demo-kurti", "title": "Cotton Straight Kurti Set",
            "title_ta": "காட்டன் ஸ்ட்ரெய்ட் குர்தி செட்", "category": "Fashion",
            "price": 399, "mrp": 999, "rating": 4.3, "orders_count": 12400,
            "commission_percent": 10, "return_risk": "medium", "demo": True,
            "affiliate_url": "https://www.meesho.com/search?q=" + quote_plus("cotton kurti set"),
            "image_url": _demo_image("KURTI", "#f97316", "#db2777"),
            "features": ["Soft cotton fabric", "Daily wear-க்கு perfect", "5 colours available"],
            "cautions": ["Size chart பார்த்து order பண்ணுங்க", "Colour slightly vary ஆகலாம்"],
        },
        {
            "external_id": "demo-bottle", "title": "Stainless Steel Water Bottle 1L",
            "title_ta": "ஸ்டீல் வாட்டர் பாட்டில் 1 லிட்டர்", "category": "Home & Kitchen",
            "price": 299, "mrp": 699, "rating": 4.4, "orders_count": 18600,
            "commission_percent": 8, "return_risk": "low", "demo": True,
            "affiliate_url": "https://www.meesho.com/search?q=" + quote_plus("steel water bottle 1 litre"),
            "image_url": _demo_image("BOTTLE", "#0284c7", "#0d9488"),
            "features": ["1 litre capacity", "Leak-proof cap", "Office/college-க்கு easy"],
            "cautions": ["Hot water-க்கு முன் test பண்ணுங்க", "Hand wash recommended"],
        },
        {
            "external_id": "demo-lamp", "title": "LED Study Table Lamp",
            "title_ta": "LED ஸ்டடி டேபிள் லேம்ப்", "category": "Electronics",
            "price": 499, "mrp": 1299, "rating": 4.2, "orders_count": 7600,
            "commission_percent": 12, "return_risk": "medium", "demo": True,
            "affiliate_url": "https://www.meesho.com/search?q=" + quote_plus("led study table lamp"),
            "image_url": _demo_image("LAMP", "#7c3aed", "#f59e0b"),
            "features": ["3 brightness modes", "USB charging", "Kids study-க்கு useful"],
            "cautions": ["Plug type check பண்ணுங்க", "Warranty card பாருங்க"],
        },
        {
            "external_id": "demo-storage", "title": "Kitchen Storage Container Set",
            "title_ta": "கிச்சன் ஸ்டோரேஜ் கண்டெய்னர் செட்", "category": "Home & Kitchen",
            "price": 349, "mrp": 899, "rating": 4.3, "orders_count": 9800,
            "commission_percent": 9, "return_risk": "low", "demo": True,
            "affiliate_url": "https://www.meesho.com/search?q=" + quote_plus("kitchen storage container set"),
            "image_url": _demo_image("STORAGE", "#16a34a", "#0284c7"),
            "features": ["6-piece set", "Air-tight lids", "Kitchen organisation easy"],
            "cautions": ["Size measurement பாருங்க", "Microwave-safe label check"],
        },
    ]
    created = []
    for item in products:
        created.append(upsert_product(item, source="demo"))
    return {"seeded": len(created), "products": [{"id": p["id"], "title": p["title"]} for p in created]}


if __name__ == "__main__":
    import sys
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "seed":
        print(json.dumps(seed_demo(), ensure_ascii=False, indent=2))
    elif command == "analytics":
        print(json.dumps(analytics(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(list_products(), ensure_ascii=False, indent=2))
