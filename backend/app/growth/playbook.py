"""Rotating hook / call-to-action copy for the growth agent.

Pure data + pure functions (no I/O, no imports from the renderer) so both the
render pipeline and the growth agent can use it without a circular import.

The point of the rotation is *variety*: a channel that asks for a subscribe the
same way every single day stops being noticed. Each show gets a small pool of
openers ("hook") and closers ("cta") and one is picked deterministically from
the date, so the slate changes daily but a given day is always reproducible.
"""
from datetime import date
from hashlib import sha1

# Openers shown in the accent pill during the first ~3s of a video.
HOOKS = {
    "history": [
        "இன்றைய வரலாறு",
        "இன்று நடந்தது என்ன?",
        "வரலாற்றில் இன்று",
    ],
    "make-money": [
        "இன்றைய பண யோசனை",
        "வருமானம் பெருக்க",
        "இன்று சம்பாதிக்க",
    ],
    "indian-law": [
        "இன்றைய சட்டம்",
        "உங்க உரிமை தெரியுமா?",
        "தெரிஞ்சா தப்பிக்கலாம்",
    ],
    "thirukkural": [
        "இன்றைய குறள்",
        "வள்ளுவர் சொல்கிறார்",
        "இன்று ஒரு குறள்",
    ],
    "english": [
        "இன்றைய ஆங்கிலம்",
        "இன்று 3 வாக்கியம்",
        "English made easy",
    ],
    "gk": [
        "இன்றைய தகவல்",
        "இது தெரியுமா?",
        "அறிய தகவல்கள்",
    ],
    "kids": [
        "குழந்தைகள் கற்றல்",
        "இன்று கற்போம்",
        "சின்ன பிள்ளை பாடம்",
    ],
    "health": [
        "இன்றைய ஆரோக்கியம்",
        "உடம்பை காப்போம்",
        "இன்று 3 குறிப்பு",
    ],
    "motivation": [
        "இன்றைய பாடம்",
        "வாழ்க்கை பாடம்",
        "இன்று ஒரு நம்பிக்கை",
    ],
    "news": [
        "இன்றைய செய்திகள்",
        "முக்கிய செய்திகள்",
        "நாளைய செய்தி",
    ],
}

# Closers used on the animated end-card tagline.
CTAS = [
    "தினமும் புது வீடியோ · Like · Share · Subscribe",
    "Subscribe பண்ணா தினமும் வீடியோ வரும்",
    "Like · Share · Subscribe — நம்ம channel-ஐ வளர்ப்போம்",
    "Subscribe + Bell 🔔 — புது வீடியோ மிஸ் ஆகாது",
]

# Extra hashtags rotated onto uploads so each post reaches a slightly different
# audience without looking spammy.
HASHTAG_PACKS = [
    ["#Tamil", "#TamilVideos", "#DailyTamil"],
    ["#TamilContent", "#Shorts", "#TamilShorts"],
    ["#TamilLearning", "#TamilFacts", "#Trending"],
    ["#TamilMotivation", "#LearnTamil", "#Viral"],
]

DEFAULT_HOOK = "இன்றைய வீடியோ"


def _seed(kind: str, day: str) -> int:
    digest = sha1(f"{kind}:{day}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def variant_for(kind: str, day: str | None = None) -> dict:
    """Deterministic daily hook / cta / hashtag pack for one show."""
    day = day or date.today().isoformat()
    seed = _seed(kind, day)
    hooks = HOOKS.get(kind) or [DEFAULT_HOOK]
    return {
        "hook": hooks[seed % len(hooks)],
        "cta": CTAS[(seed // 7) % len(CTAS)],
        "hashtags": HASHTAG_PACKS[(seed // 13) % len(HASHTAG_PACKS)],
        "day": day,
    }
