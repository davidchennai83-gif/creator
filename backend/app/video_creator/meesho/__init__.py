"""Daily Tamil Budget Finds video script from the Meesho catalogue.

The script is deliberately short: hook, product and price, why it was picked,
one honest caution, then the click/order call to action. It uses the same scene
renderer as the other shows, with an optional product-image card.
"""
from __future__ import annotations

import logging
import zlib
from datetime import date

from app import affiliate, finds
from app.config.settings import settings

log = logging.getLogger(__name__)

# Rotating honest hooks for the deterministic template, so the channel does not
# open every day with the same line. {price} is the catalogue price.
TEMPLATE_HOOKS = (
    "{price}-ல இதான் best",
    "{price} budget-ல இதைப் பாருங்க",
    "{price}-க்கு இந்த product எப்படி?",
    "இன்றைய {price} Budget Pick",
    "{price}-ல கிடைக்கும் ஒரு option",
)
DISCLOSURE_LINE = "Affiliate link: வாங்கினால் எனக்கு commission கிடைக்கும்"
DISCLOSURE_SPEECH = "இது ஒரு அஃபிலியேட் லிங்க். நீங்கள் வாங்கினால் எனக்கு சிறிய கமிஷன் கிடைக்கும்."


def _inr(value) -> str:
    try:
        return f"₹{float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "₹0"


def _rating(value) -> float:
    try:
        return max(0.0, min(5.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


def _discount_pct(price, mrp) -> int:
    try:
        price, mrp = float(price or 0), float(mrp or 0)
    except (TypeError, ValueError):
        return 0
    return int(round((mrp - price) / mrp * 100)) if mrp > price > 0 else 0


def _hook_for(product: dict, day: date, price: str) -> str:
    """Stable per product+day (a re-render gives the same hook), varied across days."""
    seed = zlib.crc32(f"{product.get('id')}|{day.isoformat()}".encode("utf-8"))
    return TEMPLATE_HOOKS[seed % len(TEMPLATE_HOOKS)].format(price=price)


def _short(text, limit=74) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def create_script(day: date, progress):
    progress("Choosing today's budget product")
    product = finds.today_pick(day)
    if not product:
        raise ValueError(
            "No active affiliate products. Add products in Finds admin, then try again."
        )
    # Strict mode is an honesty guard, not just a dashboard warning: a sample
    # product must not become a rendered video that the schedules can upload.
    from app import finds_agent
    if finds_agent.load_config().get("require_affiliate_link"):
        check = finds_agent.monetization(product)
        if not check["ready"]:
            raise ValueError(
                "Strict affiliate mode: today's product has no commission-ready link ("
                + "; ".join(check["issues"]) + ")."
            )

    title = product.get("title_ta") or product.get("title") or "Budget product"
    title_en = product.get("title") or title
    price = _inr(product.get("price"))
    mrp = _inr(product.get("mrp"))
    rating = _rating(product.get("rating"))
    pct = _discount_pct(product.get("price"), product.get("mrp"))
    orders = int(product.get("orders_count") or 0)
    category = product.get("category") or "Shopping"
    features = [x for x in (product.get("features") or []) if str(x).strip()]
    cautions = [x for x in (product.get("cautions") or []) if str(x).strip()]
    if not features:
        features = ["Budget price", "Online reviews நல்லா இருக்கு"]
    if not cautions:
        cautions = ["Size / colour check பண்ணுங்க", "Return policy பாருங்க"]

    base = settings.FINDS_PUBLIC_BASE_URL.rstrip("/")
    short_url = f"{base}/go/{product['id']}"
    store = affiliate.order_label(product.get("affiliate_url"), "Meesho")
    store_ta = "மீஷோவில்" if store.lower() == "meesho" else f"{store}-ல"
    common = {
        "product_id": product["id"],
        "product_title": title_en,
        "product_title_ta": title,
        "category": category,
        "price": product.get("price"),
        "mrp": product.get("mrp"),
        "rating": rating,
        "discount_pct": pct,
        "orders_count": orders,
        "features": features[:4],
        "cautions": cautions[:3],
        "short_url": short_url,
        "affiliate_url": product.get("affiliate_url"),
        "demo": bool(product.get("demo")),
    }

    price_line = f"{price}  (MRP {mrp})" + (f" · {pct}% off" if pct >= 10 else "")
    points = [
        {
            **common,
            "title": "இன்றைய Budget Pick",
            "lines": ["Tamil Budget Finds", _hook_for(product, day, price)],
            "speech": f"இன்றைய பட்ஜெட் தேர்வு. இந்த பொருளின் விலை {price}.",
            "topic": "wallet",
            "photo_query": "online shopping sale bags",
            "text": f"Tamil Budget Finds. {price} budget product pick.",
        },
        {
            **common,
            "title": _short(title, 64),
            "title_en": title_en,
            "lines": ([price_line, f"{rating:.1f}★ · {orders:,}+ orders"]
                      if orders > 0 else
                      [price_line, f"{rating:.1f}★ rating"]),
            "speech": ((f"{title}. விலை {price}. எம்.ஆர்.பி. {mrp}. "
                        f"மதிப்பீடு {rating:.1f} நட்சத்திரம். {orders} ஆர்டர்களுக்கு மேல்.")
                       if orders > 0 else
                       (f"{title}. விலை {price}. எம்.ஆர்.பி. {mrp}. "
                        f"மதிப்பீடு {rating:.1f} நட்சத்திரம்.")),
            "topic": "consumer",
            "photo_query": f"{category} product",
            "image_url": product.get("image_url") or "",
            "text": ((f"{title_en}. Price {price}, MRP {mrp}. Rating {rating:.1f} stars, {orders} orders.")
                     if orders > 0 else
                     f"{title_en}. Price {price}, MRP {mrp}. Rating {rating:.1f} stars."),
        },
        {
            **common,
            "title": "ஏன் இந்த Product?",
            "lines": [_short(x) for x in features[:2]],
            "speech": "ஏன் இந்த பொருள்? " + " ".join(
                _short(x, 40).rstrip(".!?") + "." for x in features[:2] if x
            ),
            "topic": "consumer",
            "photo_query": "quality check parcel",
            "text": "Why this product: " + " ".join(features[:2]),
        },
        {
            **common,
            "title": "வாங்கும் முன் கவனிக்க",
            "lines": [_short(x) for x in cautions[:2]],
            "speech": "வாங்கும் முன் இதை கவனிக்கவும். " + " ".join(
                _short(x, 40).rstrip(".!?") + "." for x in cautions[:2] if x
            ),
            "topic": "warning",
            "photo_query": "parcel delivery box",
            "text": "Before buying: " + " ".join(cautions[:2]),
        },
        {
            **common,
            "title": "எப்படி Order பண்றது?",
            "lines": ["Bio link-ல click பண்ணுங்க", f"{store}-ல order பண்ணுங்க"],
            "speech": f"பயோ லிங்கில் கிளிக் செய்து ஆர்டர் செய்யுங்கள். {store_ta} ஆர்டர் செய்யுங்கள்.",
            "topic": "delivery",
            "photo_query": "delivery courier package",
            "links": [{"title": f"Buy on {store}", "link": short_url}],
            "text": f"Click the link to buy on {store}. {short_url}",
        },
    ]
    # Disclosure: a real affiliate link means we earn commission. Say so on screen,
    # in the voice-over and in the caption text. Skipped for sample products.
    if getattr(settings, "MEESHO_DISCLOSURE", True) and not product.get("demo"):
        cta = points[4]
        cta["disclosure"] = DISCLOSURE_LINE
        cta["lines"] = [*cta["lines"], DISCLOSURE_LINE]
        cta["speech"] = f"{cta['speech']} {DISCLOSURE_SPEECH}"
        cta["text"] = f"{cta['text']} (Affiliate link - I may earn a commission.)"
    if getattr(settings, "MEESHO_AI_COPY", False):
        try:
            from app.video_creator.meesho import ai_copy

            progress("Writing Tamil hook and benefits with the local AI model")
            copy = ai_copy.generate_copy(product)
            if copy:
                points = ai_copy.apply_copy(points, copy, product)
                progress("AI copy applied; catalogue facts kept as the fallback")
            else:
                progress("AI copy unavailable; using the deterministic template")
        except Exception as exc:
            log.warning("Meesho AI copy failed, keeping template: %s", exc)
            progress("AI copy skipped; using the deterministic template")

    progress(f"Product selected: {title_en} (Rs {price.replace('₹', '').strip()})")
    return points
