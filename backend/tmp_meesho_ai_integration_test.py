import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config.settings import settings
from app.video_creator.meesho import create_script
from app.video_creator.meesho import ai_copy

DAY = date(2026, 10, 23)


def show(label, points):
    print(f"\n=== {label} ===")
    for i, point in enumerate(points, 1):
        print(f"{i}. {point.get('title')}")
        for line in point.get("lines") or []:
            print("   -", line)


print("--- sanitizer test ---")
fake = {
    "hook_ta": "இன்றைய சூப்பர் ஆஃபர்! 100% உறுதி",
    "benefits_ta": [
        "ஆறு துண்டுகள் கொண்ட தொகுப்பு",
        "உணவு கெட்டுப்போகாது",
        "சமையலறை ஒழுங்கமைப்பது எளிது",
    ],
    "caution_ta": "பாதுகாப்பானது",
    "cta_ta": "இப்போதே 50% off-க்கு order பண்ணுங்க",
}
product = {
    "title": "Kitchen Storage Container Set",
    "price": 349,
    "mrp": 699,
    "rating": 4.3,
    "orders_count": 9800,
    "features": ["6-piece set", "Air-tight lids", "Kitchen organisation easy"],
    "cautions": ["Size measurement பாருங்க", "Microwave-safe label check"],
}
safe = ai_copy.sanitize_copy(fake, product)
print(json.dumps(safe, ensure_ascii=False, indent=2))
assert "100%" not in safe["hook_ta"]
assert "உறுதி" not in safe["hook_ta"]
assert safe["benefits_ta"][1] == "Air-tight lids"
assert "50" not in safe["cta_ta"]
print("SANITIZER PASS")

settings.MEESHO_AI_COPY = False
show("deterministic (default)", create_script(DAY, print))

settings.MEESHO_AI_COPY = True
show("AI copy enabled", create_script(DAY, print))
