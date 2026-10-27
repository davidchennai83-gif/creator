import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from app import finds

PRODUCT_IDS = ["M16B251532897", "M1CB98D574599"]
MODEL = "gemma3:4b"

SCHEMA = {
    "type": "object",
    "properties": {
        "hook_ta": {"type": "string"},
        "benefits_ta": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "caution_ta": {"type": "string"},
        "cta_ta": {"type": "string"},
    },
    "required": ["hook_ta", "benefits_ta", "caution_ta", "cta_ta"],
}

TAMIL = re.compile(r"[\u0b80-\u0bff]")


def build_prompt(product):
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
    return (
        "You are a Tamil budget-shopping host. Write a 25-30 second YouTube Shorts script. "
        "Use ONLY the facts supplied. Do not invent specifications, reviews, discounts, "
        "health claims, guarantees, or consequences that are not in the facts. "
        "Each benefit line must restate exactly one supplied feature, without adding a new "
        "claim. The caution must come from the supplied cautions. "
        "Do not use these words: best, guarantee, 100%, cure, limited time, today only. "
        "Return JSON only.\n"
        "Fields:\n"
        "- hook_ta: one spoken Tamil hook, max 80 characters, about the everyday problem "
        "(not a false urgency)\n"
        "- benefits_ta: exactly 3 spoken Tamil lines, max 70 characters each, one per feature\n"
        "- caution_ta: one honest Tamil caution, max 80 characters\n"
        "- cta_ta: one short Tamil call to action, max 60 characters, tell viewers to use the "
        "link in the description\n"
        "Use Tamil script. Natural spoken Tamil. No emojis, no URLs, no new numbers.\n"
        "FACTS:\n" + json.dumps(facts, ensure_ascii=False)
    )


def check_copy(data):
    problems = []
    for key in ("hook_ta", "caution_ta", "cta_ta"):
        value = str(data.get(key) or "").strip()
        if not value:
            problems.append(f"{key} empty")
        elif not TAMIL.search(value):
            problems.append(f"{key} not Tamil script")
        elif len(value) > 100:
            problems.append(f"{key} too long: {len(value)}")
    benefits = data.get("benefits_ta") or []
    if len(benefits) != 3:
        problems.append(f"benefits count {len(benefits)}")
    for i, line in enumerate(benefits, 1):
        line = str(line or "").strip()
        if not line:
            problems.append(f"benefit {i} empty")
        elif not TAMIL.search(line):
            problems.append(f"benefit {i} not Tamil script")
        elif len(line) > 90:
            problems.append(f"benefit {i} too long: {len(line)}")
    return problems


for index, product_id in enumerate(PRODUCT_IDS, 1):
    product = finds.get_product(product_id)
    print(f"\n=== PRODUCT {index}: {product['title']} ===")
    prompt = build_prompt(product)
    started = time.time()
    try:
        with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
            response = client.post("http://127.0.0.1:11434/api/chat", json={
                "model": MODEL,
                "stream": False,
                "think": False,
                "format": SCHEMA,
                "keep_alive": "10m",
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.35, "num_predict": 700, "num_ctx": 4096},
            })
            response.raise_for_status()
        data = response.json()
        print("ELAPSED", round(time.time() - started, 1), "s")
        content = data.get("message", {}).get("content", "")
        parsed = json.loads(content)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        problems = check_copy(parsed)
        print("VALIDATION", "PASS" if not problems else problems)
    except Exception as exc:
        print("ERROR", type(exc).__name__, str(exc)[:1000])
