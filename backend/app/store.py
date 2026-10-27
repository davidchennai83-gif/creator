"""CreatorMart store backend.

Three capabilities, all self-contained on SQLite (no external services):

1. Own products  - the owner's own inventory, sold here. Cart + checkout with
   UPI intent (upi:// deep link) or Cash on Delivery.
2. Affiliate links - commission products (Amazon/Flipkart/…). The site shows
   them and redirects shoppers to the affiliate URL; no cart.
3. Order fulfilment - Cash collection and safe delivery via an external
   delivery partner: Placed -> Shipped (handed to partner) -> Delivered.
"""

import html as _html
import ipaddress
import json
import re
import socket
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from app.config.settings import settings

STORE_DIR = Path(settings.STORAGE_PATH) / "store"
DB = STORE_DIR / "orders.sqlite3"
IST = timezone(timedelta(minutes=330))

GRADIENTS = [
    "from-orange-400 to-red-500", "from-cyan-400 to-blue-600", "from-emerald-400 to-teal-600",
    "from-violet-500 to-purple-700", "from-pink-400 to-rose-600", "from-amber-400 to-orange-600",
    "from-sky-400 to-blue-600", "from-lime-400 to-green-600", "from-indigo-600 to-slate-800",
]

DEFAULT_SETTINGS = {
    "merchant_name": "CreatorMart",
    "upi_id": "",
    "partner_name": "",
    "partner_phone": "",
    "amazon_tag": "",
    "flipkart_affid": "",
}

# Seed listing: the original demo catalogue becomes the owner's own products.
SEED = [
    dict(id="m1", name="PrimeMax X20 5G (256 GB)", category="Mobiles", price=18999, mrp=24999, rating=4.4, reviews=2340, emoji="📱",
         tagline="6.7\" AMOLED 120Hz · 50MP camera · 5000 mAh", highlight="Dimensity 8100 chipset, 120Hz curved AMOLED, 67W fast charging",
         features=["Dimensity 8100 chipset", "120Hz curved AMOLED", "67W fast charging"], delivery_days=2, stock=50),
    dict(id="m2", name="NovaLite A12 (128 GB)", category="Mobiles", price=9499, mrp=12999, rating=4.1, reviews=1120, emoji="📱",
         tagline="Daylong battery · HD+ display · Clean Android", highlight="6000 mAh battery, expandable storage, 3 years updates",
         features=["6000 mAh battery", "Expandable storage", "3 years updates"], delivery_days=3, stock=40),
    dict(id="m3", name="TechOne ZenFold Pro", category="Mobiles", price=64999, mrp=74999, rating=4.6, reviews=412, emoji="📱",
         tagline="Foldable 7.8\" LTPO display · Flagship camera", highlight="Foldable AMOLED, 12 GB RAM, IP68 water resistance",
         features=["Foldable AMOLED", "12 GB RAM", "IP68 water resistance"], delivery_days=4, stock=5),
    dict(id="m4", name="SoundPod P1 (64 GB)", category="Mobiles", price=5299, mrp=6999, rating=4.0, reviews=890, emoji="📱",
         tagline="Lightweight music phone · FM + dual SIM", highlight="6.2\" HD+ display, dedicated FM radio, 3.5mm jack",
         features=["6.2\" HD+ display", "Dedicated FM radio", "3.5mm jack"], delivery_days=3, stock=30),
    dict(id="e1", name="AirBuds Pro+ ANC White", category="Electronics", price=2499, mrp=4999, rating=4.5, reviews=5210, emoji="🎧",
         tagline="Active noise cancelling · 36 hr battery", highlight="Hybrid ANC -42dB, low-lag game mode, wireless charging case",
         features=["Hybrid ANC -42dB", "Low-lag game mode", "Wireless charging case"], delivery_days=1, stock=100),
    dict(id="e2", name="SmartBand Fit S (Midnight)", category="Electronics", price=1899, mrp=3499, rating=4.2, reviews=3120, emoji="⌚",
         tagline="SpO2, heart rate, 120+ sports modes", highlight="1.8\" always-on AMOLED, 5 ATM water resistant, 10 day battery",
         features=["1.8\" always-on AMOLED", "5 ATM water resistant", "10 day battery"], delivery_days=1, stock=80),
    dict(id="e3", name="4K Ultra Smart TV 55\"", category="Electronics", price=32999, mrp=44999, rating=4.3, reviews=960, emoji="📺",
         tagline="4K HDR10+ · Dolby Audio · Smart OS", highlight="55\" 4K panel, Google TV built-in, 3 HDMI + 2 USB",
         features=["55\" 4K panel", "Google TV built-in", "3 HDMI + 2 USB"], delivery_days=5, stock=6),
    dict(id="e4", name="Boom X Bluetooth Speaker", category="Electronics", price=1799, mrp=2999, rating=4.4, reviews=2040, emoji="🔊",
         tagline="16W punchy bass · IPX7 waterproof", highlight="16W stereo output, 20 hr playtime, TWS pairing",
         features=["16W stereo output", "20 hr playtime", "TWS pairing"], delivery_days=2, stock=70),
    dict(id="f1", name="Men Wrinkle-Free Formal Shirt", category="Fashion", price=649, mrp=1299, rating=4.2, reviews=3456, emoji="👔",
         tagline="Soft cotton lycra · Office ready fits", highlight="Wrinkle-free finish, sizes 38-44, machine wash",
         features=["Wrinkle-free finish", "Sizes 38-44", "Machine wash"], delivery_days=2, stock=120),
    dict(id="f2", name="Women Floral Kurta Set", category="Fashion", price=799, mrp=1599, rating=4.3, reviews=2780, emoji="👗",
         tagline="Breathable georgette · Comes with dupatta", highlight="Soft georgette, M-XXL sizes, fully stitched",
         features=["Soft georgette", "M-XXL sizes", "Fully stitched"], delivery_days=3, stock=90),
    dict(id="f3", name="GripRun Sports Shoes", category="Fashion", price=1499, mrp=3299, rating=4.1, reviews=4234, emoji="👟",
         tagline="Cushioned sole · Breathable mesh upper", highlight="EVA cushioned sole, anti-slip grip, UK 6-11 sizes",
         features=["EVA cushioned sole", "Anti-slip grip", "UK 6-11 sizes"], delivery_days=2, stock=60),
    dict(id="h1", name="Non-Stick Cookware Set (5 pc)", category="Home & Kitchen", price=1299, mrp=2999, rating=4.4, reviews=1876, emoji="🍳",
         tagline="Granite non-stick · Induction friendly", highlight="5-piece set, free ladle included, PFOA free",
         features=["5-piece set", "Free ladle included", "PFOA free"], delivery_days=4, stock=45),
    dict(id="h2", name="Insulated Steel Bottle 1L", category="Home & Kitchen", price=549, mrp=999, rating=4.3, reviews=2311, emoji="🍶",
         tagline="24 hr cold / 12 hr hot · Leak-proof cap", highlight="304 steel, powder coated finish, 5 yr warranty",
         features=["304 steel", "Powder coated finish", "5 yr warranty"], delivery_days=2, stock=150),
    dict(id="h3", name="Queen Fitted Comforter Set", category="Home & Kitchen", price=2199, mrp=4599, rating=4.0, reviews=890, emoji="🛏️",
         tagline="Microfibre bedding · 7 pc combo", highlight="7-piece combo, all-season fill, washable cover",
         features=["7-piece combo", "All-season fill", "Washable cover"], delivery_days=5, stock=25),
    dict(id="b1", name="Vitamin C Glow Serum 30ml", category="Beauty", price=499, mrp=999, rating=4.3, reviews=1234, emoji="✨",
         tagline="10% Vitamin C · Brightens & evens tone", highlight="Dermatologist tested, cruelty free, SPF safe",
         features=["Dermatologist tested", "Cruelty free", "SPF safe"], delivery_days=1, stock=200),
    dict(id="b2", name="Self-Growth Bestseller Book Pack", category="Books", price=799, mrp=1599, rating=4.7, reviews=3890, emoji="📚",
         tagline="3 timeless bestsellers in one pack", highlight="English editions, original prints, gift packing",
         features=["English editions", "Original prints", "Gift packing"], delivery_days=3, stock=55),
]


def _db():
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS clicks (product_id TEXT NOT NULL, at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    _seed_products(db)
    return db


def _seed_products(db):
    # Seed exactly once. Checking COUNT(*)==0 would resurrect the demo catalogue
    # after the owner deliberately deletes every product.
    if db.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone():
        return
    count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count:
        db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('seeded', '1')")
        db.commit()
        return
    for i, item in enumerate(SEED):
        body = {
            "kind": "own", "published": True,
            "gradient": GRADIENTS[i % len(GRADIENTS)],
            "affiliate_url": "", "platform": "", "emi_3": round(item["price"] / 3),
            **item,
        }
        db.execute("INSERT OR REPLACE INTO products (id, body) VALUES (?,?)", (body["id"], json.dumps(body)))
    db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('seeded', '1')")
    db.commit()


def _now_utc():
    return datetime.now(timezone.utc).isoformat()


def _now_ist():
    return datetime.now(IST).isoformat(timespec="seconds")


# ------------------------------------------------------------------ products

def _live(p: dict) -> dict:
    """Serve-time affiliate URL refresh: re-apply the configured tag (plain, untagged
    links added before the tag was set get tagged automatically)."""
    out = dict(p)
    if out.get("kind") == "affiliate" and out.get("affiliate_url"):
        out["affiliate_url"] = affiliateize(out["affiliate_url"])
    return out


def catalog() -> list[dict]:
    db = _db()
    rows = db.execute("SELECT body FROM products").fetchall()
    db.close()
    out = [json.loads(r[0]) for r in rows if json.loads(r[0]).get("published", True)]
    out = [_live(p) for p in out]
    out.sort(key=lambda p: (-(p.get("reviews") or 0), p["id"]))
    return out


def get_product(product_id: str) -> dict | None:
    db = _db()
    row = db.execute("SELECT body FROM products WHERE id=?", (str(product_id),)).fetchone()
    db.close()
    return _live(json.loads(row[0])) if row else None


def save_product(data: dict) -> dict:
    """Insert or update a product. Only shop-owned (kind=own) products are sold here."""
    db = _db()
    pid = str(data.get("id") or "").strip() or "P" + uuid.uuid4().hex[:6].upper()
    existing = db.execute("SELECT body FROM products WHERE id=?", (pid,)).fetchone()
    previous = json.loads(existing[0]) if existing else {}
    body = {
        "id": pid,
        "kind": "own" if str(data.get("kind", "own")) != "affiliate" else "affiliate",
        "name": str(data.get("name", "")).strip() or "Untitled",
        "category": str(data.get("category", "General")).strip() or "General",
        "price": max(0, int(data.get("price") or 0)),
        "mrp": max(0, int(data.get("mrp") or 0)),
        "rating": float(data.get("rating") or 4.0),
        "reviews": int(data.get("reviews") or 0),
        "emoji": str(data.get("emoji") or "🛍️")[:4],
        "gradient": str(data.get("gradient") or "").strip() or previous.get("gradient")
                    or GRADIENTS[uuid.uuid4().int % len(GRADIENTS)],
        "tagline": str(data.get("tagline", "")).strip(),
        "highlight": str(data.get("highlight", "")).strip(),
        "features": [str(f).strip() for f in (data.get("features") or []) if str(f).strip()][:8],
        "delivery_days": max(1, int(data.get("delivery_days") or 3)),
        "emi_3": max(0, int(data.get("emi_3") or round((data.get("price") or 0) / 3))),
        "stock": max(0, int(data.get("stock") or 0)),
        "affiliate_url": str(data.get("affiliate_url", "")).strip(),
        "platform": str(data.get("platform", "")).strip(),
        "published": bool(data.get("published", True)),
        "created": previous.get("created") or _now_utc(),
    }
    if body["mrp"] < body["price"]:
        body["mrp"] = body["price"]
    if body["kind"] == "affiliate":
        raw = body["affiliate_url"]
        body["raw_url"] = raw
        body["affiliate_url"] = affiliateize(raw)
        if not body.get("platform"):
            body["platform"] = detect_platform(raw)
    db.execute("INSERT OR REPLACE INTO products (id, body) VALUES (?,?)", (pid, json.dumps(body)))
    db.commit()
    db.close()
    return body


def admin_products() -> list[dict]:
    db = _db()
    rows = db.execute("SELECT body FROM products").fetchall()
    db.close()
    items = [json.loads(r[0]) for r in rows]
    # published lives inside the JSON body; sort in Python (live first, newest last-inserted last)
    items.sort(key=lambda p: (not bool(p.get("published", False)),))
    return items


def set_product_published(pid: str, published: bool) -> bool:
    db = _db()
    row = db.execute("SELECT body FROM products WHERE id=?", (pid,)).fetchone()
    if not row:
        db.close()
        return False
    body = json.loads(row[0])
    body["published"] = published
    db.execute("INSERT OR REPLACE INTO products (id, body) VALUES (?,?)", (pid, json.dumps(body)))
    db.commit()
    db.close()
    return True


def delete_product(pid: str) -> bool:
    db = _db()
    cur = db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    db.close()
    return cur.rowcount > 0


# ------------------------------------------------------------------ settings

def settings_get() -> dict:
    db = _db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    db.close()
    merged = dict(DEFAULT_SETTINGS)
    merged.update({k: v for k, v in rows})
    return merged


def settings_set(patch: dict) -> dict:
    db = _db()
    for key in ("upi_id", "merchant_name", "partner_name", "partner_phone", "amazon_tag", "flipkart_affid"):
        if key in patch:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                       (key, str(patch[key]).strip()))
    db.commit()
    db.close()
    return settings_get()


def detect_platform(url: str) -> str:
    """Best-effort retailer name from a deal URL host (Amazon/Flipkart/Meesho/…)."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parts = url.split("/")
    if len(parts) < 3:
        return ""
    host = re.sub(r"^www\.", "", parts[2].lower())
    return next((v for k, v in PLATFORM_HINTS.items() if k in host), "")


def _with_param(url: str, key: str, value: str) -> str:
    """Set/replace a query param on a URL, keeping the rest of the query intact."""
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def affiliateize(url: str) -> str:
    """Apply the configured affiliate tag/affid to a deal URL.

    Amazon Associates links use tag=…, Flipkart Affiliate links use affid=…. When
    the owner has configured a tag, it becomes the source of truth: plain product
    links, existing tags — all get their tag set to the configured value. With no
    tag configured, the URL is returned unchanged so links can be added early.
    """
    url = (url or "").strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    low = url.lower()
    if "amazon" in low:
        tag = settings_get().get("amazon_tag", "").strip()
        return _with_param(url, "tag", tag) if tag else url
    if "flipkart" in low:
        affid = settings_get().get("flipkart_affid", "").strip()
        return _with_param(url, "affid", affid) if affid else url
    return url


def readiness() -> dict:
    """Go-live checklist: what the owner still has to provide/do for the store."""
    s = settings_get()
    items = [json.loads(r[0]) for r in _db().execute("SELECT body FROM products").fetchall()]
    return {
        "upi_id": bool(s.get("upi_id", "").strip()),
        "amazon_tag": bool(s.get("amazon_tag", "").strip()),
        "flipkart_affid": bool(s.get("flipkart_affid", "").strip()),
        "has_own": any(p.get("kind") == "own" and p.get("published") for p in items),
        "has_affiliate": any(p.get("kind") == "affiliate" and p.get("published") for p in items),
        "merchant_name": s.get("merchant_name", "CreatorMart").strip() or "CreatorMart",
        "partner_name": s.get("partner_name", "").strip(),
    }


def upi_intent(amount: int, order_id: str) -> str | None:
    """Build a upi:// deep link from the configured UPI id (None if not set)."""
    upi = settings_get().get("upi_id", "").strip()
    if not upi:
        return None
    merchant = settings_get().get("merchant_name", "CreatorMart").strip() or "CreatorMart"
    return (f"upi://pay?pa={upi}&pn={merchant}&am={amount}&cu=INR&tn={order_id}"
            .replace(" ", "%20"))


# ------------------------------------------------------------------ orders

def place_order(owner: str, items: list[dict], customer: dict, payment: str) -> dict:
    """Validate against the DB (server-side prices), decrement stock, record order."""
    db = _db()
    lines: list[dict] = []
    subtotal = 0
    try:
        # One write transaction: aggregate duplicate cart lines first, then
        # validate and decrement stock against the same snapshot.
        db.execute("BEGIN IMMEDIATE")
        wanted: dict[str, int] = {}
        for entry in items:
            pid = str(entry.get("id", ""))
            qty = max(1, min(int(entry.get("qty", 1)), 20))
            wanted[pid] = wanted.get(pid, 0) + qty
        for pid, qty in wanted.items():
            row = db.execute("SELECT body FROM products WHERE id=?", (pid,)).fetchone()
            product = _live(json.loads(row[0])) if row else None
            if not product or product.get("kind") != "own" or not product.get("published", True):
                raise ValueError("Product is not available for purchase here")
            stock = product.get("stock") or 0
            if stock < qty:
                raise ValueError(f"Only {stock} left in stock")
            line_total = product["price"] * qty
            subtotal += line_total
            lines.append({
                "product_id": product["id"], "name": product["name"], "emoji": product["emoji"],
                "price": product["price"], "qty": qty, "line_total": line_total,
                "delivery_days": product["delivery_days"],
            })
            db.execute("UPDATE products SET body=? WHERE id=?",
                       (json.dumps({**product, "stock": stock - qty}), product["id"]))
        if not lines:
            raise ValueError("Your cart is empty")
        delivery = 49 if subtotal < 499 else 0
        total = subtotal + delivery
        order_id = "OP" + datetime.now(IST).strftime("%Y%m%d%H%M") + "-" + uuid.uuid4().hex[:4].upper()
        pay_status = None
        status = "Placed"
        if payment == "upi":
            status, pay_status = "PaymentPending", "pending"
        order = {
            "id": order_id,
            "owner": owner,
            "created": _now_utc(),
            "items": lines,
            "customer": {k: str(customer.get(k, "")).strip() for k in ("name", "phone", "address", "city", "pincode")},
            "payment": "upi" if payment == "upi" else "cod",
            "pay_status": pay_status,
            "upi_intent": upi_intent(total, order_id) if payment == "upi" else None,
            "summary": {"subtotal": subtotal, "delivery": delivery, "total": total},
            "status": status,
            "shipment": {},
        }
        db.execute("INSERT OR REPLACE INTO orders (id, owner, body) VALUES (?,?,?)",
                   (order["id"], owner, json.dumps(order)))
        db.commit()
        return order
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def orders_for(owner: str) -> list[dict]:
    db = _db()
    rows = db.execute("SELECT body FROM orders WHERE owner=? ORDER BY rowid DESC", (owner,)).fetchall()
    db.close()
    return [json.loads(r[0]) for r in rows]


def all_orders() -> list[dict]:
    db = _db()
    rows = db.execute("SELECT body FROM orders ORDER BY rowid DESC").fetchall()
    db.close()
    return [json.loads(r[0]) for r in rows]


def _order_update(pid: str, mutate) -> dict | None:
    db = _db()
    try:
        row = db.execute("SELECT body FROM orders WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        body = json.loads(row[0])
        mutate(body)
        db.execute("INSERT OR REPLACE INTO orders (id, owner, body) VALUES (?,?,?)",
                   (body["id"], body["owner"], json.dumps(body)))
        db.commit()
        return body
    finally:
        db.close()


def mark_paid(pid: str) -> dict | None:
    def mutate(o):
        if o.get("payment") == "upi" and o.get("status") == "PaymentPending":
            o.update(status="Placed", pay_status="paid")
    return _order_update(pid, mutate)


def ship_order(pid: str, partner: str, tracking: str = "") -> dict | None:
    def mutate(o):
        if o.get("status") != "Placed":
            raise ValueError("Only placed orders can be handed to delivery")
        if o.get("payment") == "upi" and o.get("pay_status") != "paid":
            raise ValueError("Confirm the UPI payment before shipping")
        o["shipment"] = {
            "partner": (partner or settings_get().get("partner_name", "")).strip(),
            "tracking": tracking.strip(),
            "shipped_at": _now_ist(),
        }
        o["status"] = "Shipped"
    return _order_update(pid, mutate)


def deliver_order(pid: str) -> dict | None:
    def mutate(o):
        if o.get("status") != "Shipped":
            raise ValueError("Only shipped orders can be marked delivered")
        o.setdefault("shipment", {})["delivered_at"] = _now_ist()
        o["status"] = "Delivered"
    return _order_update(pid, mutate)


# ------------------------------------------------------------------ analytics

def record_click(product_id: str) -> bool:
    """Count one 'interested shopper' hit on an affiliate deal (commission funnel)."""
    db = _db()
    row = db.execute("SELECT 1 FROM products WHERE id=?", (str(product_id),)).fetchone()
    if not row:
        db.close()
        return False
    db.execute("INSERT INTO clicks (product_id, at) VALUES (?,?)", (str(product_id), _now_utc()))
    db.commit()
    db.close()
    return True


def click_counts() -> dict:
    db = _db()
    rows = db.execute("SELECT product_id, COUNT(*) FROM clicks GROUP BY product_id").fetchall()
    db.close()
    return {pid: int(n) for pid, n in rows}


def analytics() -> dict:
    """Earnings + funnel snapshot for the owner's dashboard."""
    db = _db()
    orders = [json.loads(r[0]) for r in db.execute("SELECT body FROM orders").fetchall()]
    products = [json.loads(r[0]) for r in db.execute("SELECT body FROM products").fetchall()]
    db.close()
    clicks = click_counts()

    revenue = 0          # value of orders that are at least placed (excludes pure pending UPI)
    pending = 0
    upi = cod = 0
    by_product: dict = {}
    for o in orders:
        total = int((o.get("summary") or {}).get("total") or 0)
        status = o.get("status")
        if o.get("payment") == "upi":
            upi += 1
        else:
            cod += 1
        if status in ("Placed", "Shipped", "Delivered"):
            revenue += total
        if status not in ("Delivered", "Cancelled", "Returned"):
            pending += 1
        for line in o.get("items", []):
            name = line.get("name", "?")
            agg = by_product.setdefault(name, {"qty": 0, "revenue": 0})
            agg["qty"] += int(line.get("qty") or 0)
            agg["revenue"] += int(line.get("line_total") or 0)

    live = [p for p in products if p.get("published")]
    names = {p["id"]: p.get("name", p["id"]) for p in products}
    top_products = [{"name": n, **v} for n, v in sorted(by_product.items(), key=lambda kv: -kv[1]["qty"])[:5]]
    top_clicks = [{"name": names.get(pid, pid), "clicks": n}
                  for pid, n in sorted(clicks.items(), key=lambda kv: -kv[1])[:5]]
    return {
        "orders_total": len(orders),
        "orders_pending": pending,
        "revenue_confirmed": revenue,
        "cod_orders": cod,
        "upi_orders": upi,
        "affiliate_clicks": sum(clicks.values()),
        "products_live": len(live),
        "products_affiliate": sum(1 for p in products if p.get("kind") == "affiliate"),
        "top_products": top_products,
        "top_clicks": top_clicks,
    }


# ------------------------------------------------------------------ url meta

PLATFORM_HINTS = {
    "amazon.in": "Amazon", "amazon.com": "Amazon", "flipkart.com": "Flipkart",
    "meesho.com": "Meesho", "myntra.com": "Myntra", "snapdeal.com": "Snapdeal",
}


def _is_public_http_url(url: str) -> bool:
    """Reject localhost, private/link-local IPs and non-HTTP schemes.

    The product-link importer fetches user-supplied URLs, so it must not be
    usable as an SSRF probe against the machine or the LAN.
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True


def meta_from_url(url: str) -> dict:
    """Best-effort product info from a deal URL (og: tags). Returns title/price/platform."""
    import httpx
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = re.sub(r"^www\.", "", (url.split("/")[2] if len(url.split("/")) > 2 else "")).lower()
    platform = next((v for k, v in PLATFORM_HINTS.items() if k in host), "")
    result = {"url": url, "platform": platform, "title": "", "price": None, "image": ""}
    try:
        current = url
        for _ in range(4):
            if not _is_public_http_url(current):
                result["error"] = "That link points to a private or local address."
                return result
            resp = httpx.get(current, timeout=12, follow_redirects=False,
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                                    "(KHTML, like Gecko) Chrome/148.0 Safari/537.36"})
            if resp.is_redirect and resp.headers.get("location"):
                current = urljoin(current, resp.headers["location"])
                continue
            break
        else:
            result["error"] = "Too many redirects."
            return result
        html = resp.text
    except Exception as exc:
        result["error"] = f"Could not load the link ({type(exc).__name__})"
        return result
    match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if not match:
        match = re.search(r'<meta\s+property="og:title"\s+content=\'([^\']+)\'', html)
    if match:
        result["title"] = _html.unescape(match.group(1))
    else:
        t = re.search(r"<title>([^<]+)</title>", html)
        result["title"] = t.group(1).strip()[:200] if t else ""
    pm = re.search(r'<meta\s+property="product:price:amount"\s+content="([0-9.]+)"', html)
    if pm:
        try:
            result["price"] = int(float(pm.group(1)))
        except ValueError:
            pass
    im = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if im:
        result["image"] = im.group(1)
    if not result["title"]:
        result["error"] = "Could not read the product name (the site blocked us). Type it manually."
    return result