"""Optional local-AI copy for the daily Tamil Budget Finds video.

The deterministic script in ``meesho/__init__.py`` is still the source of truth.
This module only rewrites the human-facing hook / benefit / caution / CTA lines
with a local Ollama model, and it refuses anything that is not grounded in the
product record. If the model is slow, unavailable, or writes an unsupported
claim, the caller keeps the deterministic template.

Why a separate module:
* one model call per video, not per scene;
* strict JSON schema + Tamil-script checks;
* banned-claim and new-number checks with line-level fallback;
* no API key, no per-video cost, no external data leak.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, field_validator

from app.config.settings import settings

log = logging.getLogger(__name__)

TAMIL = re.compile(r"[\u0b80-\u0bff]")
ARABIC_NUMBER = re.compile(r"\d+")

# Claims the model likes to add even when the catalogue does not support them.
# A line containing one of these is replaced with the matching catalogue fact.
BANNED_CLAIMS = (
    "கெட்டுப்போகாது",   # will not spoil
    "பாதுகாப்பானது",     # is safe
    "ஆரோக்கிய",          # health
    "உறுதி",             # guarantee / assured
    "நிச்சயம்",          # definitely
    "சிறந்த",            # best
    "100%",
    "best",
    "guarantee",
    "cure",
    "limited time",
    "today only",
    "free",
    "no.1",
    "number one",
    "instant",
    "weight loss",
)

DEFAULT_HOOK = "இன்றைய Budget Pick-ல இதைப் பாருங்க."
DEFAULT_CTA = "Description-ல உள்ள link-ல order பண்ணுங்க!"
DEFAULT_CAUTION = "Size / colour check பண்ணி order பண்ணுங்க."


class MeeshoCopy(BaseModel):
    hook_ta: str = Field(min_length=8, max_length=100)
    benefits_ta: list[str] = Field(min_length=3, max_length=3)
    caution_ta: str = Field(min_length=8, max_length=100)
    cta_ta: str = Field(min_length=8, max_length=100)

    @field_validator("hook_ta", "caution_ta", "cta_ta")
    @classmethod
    def clean_tamil_line(cls, value: str) -> str:
        value = " ".join(str(value or "").split())
        if not TAMIL.search(value):
            raise ValueError("must contain Tamil script")
        return value

    @field_validator("benefits_ta")
    @classmethod
    def clean_benefits(cls, lines: list[str]) -> list[str]:
        cleaned = []
        for line in lines:
            line = " ".join(str(line or "").split())
            if not TAMIL.search(line):
                raise ValueError("every benefit must contain Tamil script")
            if len(line) > 95:
                raise ValueError("benefit line is too long")
            cleaned.append(line)
        return cleaned


def clear_ai_model() -> None:
    """Unload the model after a batch if the caller wants the RAM back."""
    try:
        with httpx.Client(timeout=10) as client:
            client.post(
                settings.OLLAMA_BASE_URL.rstrip("/") + "/api/generate",
                json={"model": settings.MEESHO_AI_MODEL, "keep_alive": 0},
            )
    except Exception:
        pass


def discount_pct(product: dict) -> int:
    """Whole-number discount from the catalogue price and MRP (0 when unknown)."""
    try:
        price = float(product.get("price") or 0)
        mrp = float(product.get("mrp") or 0)
    except (TypeError, ValueError):
        return 0
    return int(round((mrp - price) / mrp * 100)) if mrp > price > 0 else 0


def _allowed_numbers(product: dict) -> set[str]:
    nums = set(ARABIC_NUMBER.findall(json.dumps(product, ensure_ascii=False)))
    pct = discount_pct(product)
    if pct:
        nums.add(str(pct))  # the video itself shows "NN% off"
    return nums


def _has_new_number(text: str, allowed: set[str]) -> bool:
    return any(number not in allowed for number in ARABIC_NUMBER.findall(text))


def _product_text(product: dict) -> str:
    """Everything the catalogue itself says; claims found here are grounded."""
    parts = [product.get("title"), product.get("title_ta")]
    parts += list(product.get("features") or []) + list(product.get("cautions") or [])
    return " ".join(str(p) for p in parts if p).lower()


def _claim_regex(claim: str) -> re.Pattern:
    # Whole-word match for English claims so "free" does not hit "carefree" and
    # "cure" does not hit "secure". Tamil claims have no word boundaries, so they
    # stay substring matches.
    return re.compile(r"(?<![\w])" + re.escape(claim.lower()) + r"(?![\w])")


_CLAIM_PATTERNS = [
    (claim, _claim_regex(claim) if claim.isascii() else None) for claim in BANNED_CLAIMS
]


def _has_banned_claim(text: str, grounded: str = "") -> bool:
    """True when ``text`` makes a banned claim the catalogue does not support."""
    low = (text or "").lower()
    for claim, pattern in _CLAIM_PATTERNS:
        hit = bool(pattern.search(low)) if pattern else claim.lower() in low
        if hit and claim.lower() not in grounded:
            return True
    return False


def _clean(text: str, fallback: str, allowed: set[str], grounded: str = "",
           max_len: int = 100) -> str:
    text = " ".join(str(text or "").split())
    if not text or not TAMIL.search(text) or len(text) > max_len:
        return fallback
    if _has_banned_claim(text, grounded) or _has_new_number(text, allowed):
        return fallback
    return text


def _feature_fallback(product: dict, index: int) -> str:
    features = [str(f).strip() for f in (product.get("features") or []) if str(f).strip()]
    if index < len(features):
        return features[index]
    return "Budget price-க்கு நல்ல option."


def sanitize_copy(data: dict, product: dict) -> dict:
    """Keep safe AI lines, replace unsafe lines with catalogue facts."""
    allowed = _allowed_numbers(product)
    grounded = _product_text(product)
    cautions = [str(c).strip() for c in (product.get("cautions") or []) if str(c).strip()]
    caution_fallback = cautions[0] if cautions else DEFAULT_CAUTION
    raw_benefits = data.get("benefits_ta")
    raw_benefits = list(raw_benefits) if isinstance(raw_benefits, (list, tuple)) else []

    hook = _clean(data.get("hook_ta"), DEFAULT_HOOK, allowed, grounded, 100)
    benefits = []
    for index in range(3):
        raw = raw_benefits[index] if index < len(raw_benefits) else ""
        benefits.append(_clean(raw, _feature_fallback(product, index), allowed, grounded, 95))
    caution = _clean(data.get("caution_ta"), caution_fallback, allowed, grounded, 100)
    cta = _clean(data.get("cta_ta"), DEFAULT_CTA, allowed, grounded, 100)
    return {
        "hook_ta": hook,
        "benefits_ta": benefits,
        "caution_ta": caution,
        "cta_ta": cta,
    }


def build_prompt(product: dict) -> str:
    facts = {
        "title": product.get("title") or "",
        "title_ta": product.get("title_ta") or "",
        "category": product.get("category") or "",
        "price_inr": product.get("price"),
        "mrp_inr": product.get("mrp"),
        "rating": product.get("rating"),
        "orders": product.get("orders_count"),
        "features": [str(f).strip() for f in (product.get("features") or []) if str(f).strip()],
        "cautions": [str(c).strip() for c in (product.get("cautions") or []) if str(c).strip()],
    }
    return (
        "You are a Tamil budget-shopping host. Write a 25-30 second YouTube Shorts script. "
        "Use ONLY the facts supplied. Do not invent specifications, reviews, discounts, "
        "health claims, guarantees, or consequences that are not in the facts. "
        "Each benefit line must restate exactly one supplied feature and NOTHING more. "
        "For example, if the feature is 'Air-tight lids', say only "
        "'காற்றுப்புகாத மூடிகள் இருக்கு' and do not add 'உணவு கெட்டுப்போகாது'. "
        "The caution must come from the supplied cautions. "
        "Do not use these words: best, guarantee, 100%, cure, limited time, today only, free. "
        "Return JSON only.\n"
        "Fields:\n"
        "- hook_ta: one spoken Tamil hook, max 80 characters, about the everyday problem "
        "(never use false urgency)\n"
        "- benefits_ta: exactly 3 spoken Tamil lines, max 70 characters each, one per feature\n"
        "- caution_ta: one honest Tamil caution, max 80 characters\n"
        "- cta_ta: one short Tamil call to action, max 60 characters, tell viewers to use the "
        "link in the description. A good example: 'Description-ல உள்ள link-ல order பண்ணுங்க!'\n"
        "Use Tamil script. Natural spoken Tamil; common English product words are fine. "
        "No emojis, no URLs, no new numbers.\n"
        "FACTS:\n" + json.dumps(facts, ensure_ascii=False)
    )


def _extract_json(content: str) -> dict:
    """Parse model output; tolerate code fences and text around the JSON object."""
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except ValueError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data


def _cache_file(product: dict) -> Path | None:
    """Cache key = model + prompt, so editing the product or prompt busts it."""
    try:
        from app import finds_agent

        key = hashlib.sha256(
            (settings.MEESHO_AI_MODEL + build_prompt(product)).encode("utf-8")
        ).hexdigest()[:20]
        folder = finds_agent._finds_dir() / "ai_copy"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{key}.json"
    except Exception:
        return None


def _call_ollama(product: dict) -> dict:
    prompt = build_prompt(product)
    timeout = float(getattr(settings, "MEESHO_AI_TIMEOUT", 240) or 240)
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=10)) as client:
        response = client.post(
            settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat",
            json={
                "model": settings.MEESHO_AI_MODEL,
                "stream": False,
                "think": False,
                "format": MeeshoCopy.model_json_schema(),
                "keep_alive": "15m",
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.35, "num_predict": 700, "num_ctx": 4096},
            },
        )
        response.raise_for_status()
    content = str(response.json().get("message", {}).get("content") or "")
    # Parse loosely on purpose: sanitize_copy() validates line by line, so one
    # bad line falls back to a catalogue fact instead of discarding all the copy
    # (the strict MeeshoCopy model made a single long line cost the whole call).
    return _extract_json(content)


def generate_copy(product: dict) -> dict | None:
    """Return sanitised Tamil copy, or None when AI is disabled/unavailable."""
    if not getattr(settings, "MEESHO_AI_COPY", False):
        return None
    cache = _cache_file(product)
    if cache is not None and cache.exists():
        try:
            return sanitize_copy(json.loads(cache.read_text(encoding="utf-8")), product)
        except Exception:
            pass  # unreadable cache entry: regenerate
    try:
        data = _call_ollama(product)
        copy = sanitize_copy(data, product)
    except Exception as exc:
        log.warning("Meesho AI copy unavailable, using template: %s", exc)
        return None
    if cache is not None:
        try:
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return copy


def apply_copy(points: list[dict], copy: dict, product: dict) -> list[dict]:
    """Rewrite only the human-facing lines; keep prices, links and image cards."""
    if len(points) < 5:
        return points  # unexpected layout: keep the deterministic template
    points = [dict(point) for point in points]

    points[0]["lines"] = ["Tamil Budget Finds", copy["hook_ta"]]
    points[0]["text"] = "Tamil Budget Finds. " + copy["hook_ta"]

    points[2]["lines"] = list(copy["benefits_ta"])
    points[2]["text"] = " ".join(copy["benefits_ta"])
    # Keep the spoken sentence in sync with the rewritten Tamil lines; the
    # template speech above was built from the catalogue's English features.
    points[2]["speech"] = "ஏன் இந்த பொருள்? " + " ".join(
        item.strip().rstrip(".!?") + "." for item in copy["benefits_ta"] if item.strip()
    )

    points[3]["lines"] = [copy["caution_ta"]]
    points[3]["text"] = copy["caution_ta"]
    points[3]["speech"] = "வாங்கும் முன் இதை கவனிக்கவும். " + copy["caution_ta"].strip().rstrip(".!?") + "."

    short_url = ""
    links = points[4].get("links") or []
    if links:
        short_url = str(links[0].get("link") or "")
    # Keep the template's store line: it names the real shop (Amazon, Flipkart...)
    # instead of always saying Meesho.
    old_lines = points[4].get("lines") or []
    store_line = old_lines[1] if len(old_lines) > 1 else "Meesho-ல order பண்ணுங்க"
    disclosure = points[4].get("disclosure")
    points[4]["lines"] = [copy["cta_ta"], store_line] + ([disclosure] if disclosure else [])
    points[4]["text"] = f"{copy['cta_ta']} {short_url}".strip()
    if disclosure:
        points[4]["text"] += " (Affiliate link - I may earn a commission.)"
    return points
