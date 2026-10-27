import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from app import finds

PRODUCT_ID = "M16B251532897"
product = finds.get_product(PRODUCT_ID)
print("PRODUCT", product["title"], product["price"], product["features"], product["cautions"])

facts = {
    "title": product["title"],
    "title_ta": product.get("title_ta") or "",
    "category": product["category"],
    "price_inr": product["price"],
    "mrp_inr": product["mrp"],
    "rating": product["rating"],
    "orders": product["orders_count"],
    "features": product["features"],
    "cautions": product["cautions"],
}

schema = {
    "type": "object",
    "properties": {
        "hook_ta": {"type": "string"},
        "benefits_ta": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "caution_ta": {"type": "string"},
        "cta_ta": {"type": "string"},
    },
    "required": ["hook_ta", "benefits_ta", "caution_ta", "cta_ta"],
}

prompt = (
    "You write a 30-second Tamil YouTube Shorts script for a budget shopping channel. "
    "Use ONLY the product facts below. Do not invent specifications, discounts, reviews, "
    "health claims, or guarantees. Do not use the words best, guarantee, 100%, cure, or "
    "limited-time. Return JSON only.\n"
    "Fields:\n"
    "- hook_ta: one short spoken Tamil hook, max 80 characters\n"
    "- benefits_ta: exactly 3 short spoken Tamil benefit lines, max 70 characters each, "
    "each based on a supplied feature\n"
    "- caution_ta: one honest Tamil caution, max 80 characters, based on a supplied caution\n"
    "- cta_ta: one short Tamil call to action, max 60 characters\n"
    "Use Tamil script. Natural spoken Tamil is preferred. No emojis, no URLs, no new numbers.\n"
    "FACTS:\n" + json.dumps(facts, ensure_ascii=False)
)

for model in ("gemma3:4b", "gemma4:12b"):
    print("\n=== MODEL", model, "===")
    started = time.time()
    try:
        with httpx.Client(timeout=httpx.Timeout(240, connect=10)) as client:
            response = client.post("http://127.0.0.1:11434/api/chat", json={
                "model": model,
                "stream": False,
                "think": False,
                "format": schema,
                "keep_alive": 0,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.3, "num_predict": 800, "num_ctx": 4096},
            })
            response.raise_for_status()
        data = response.json()
        print("ELAPSED", round(time.time() - started, 1), "s")
        content = data.get("message", {}).get("content", "")
        print("RAW", content[:2500])
        try:
            parsed = json.loads(content)
            print("PARSED", json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception as exc:
            print("PARSE_ERROR", exc)
    except Exception as exc:
        print("ERROR", type(exc).__name__, str(exc)[:1000])
