"""Keep the coding chat alive when the primary model hits a limit.

OpenCode ends a turn as soon as a provider answers with a rate limit, an
exhausted quota or an empty credit balance. Instead of showing that failure the
chat replays the same prompt on a local Ollama model, then returns to the
original model as soon as the cooldown expires (by then the quota has usually
recovered). The policy is deliberately small and dependency free so the bridge
can use it while it is streaming.
"""
from __future__ import annotations

import re
import time

from app.config.settings import settings

# Provider wording differs, so match the meaning instead of one exact string.
# Keeping this narrow matters: a genuine bug or an auth failure must still be
# reported, not silently replayed on another model.
_LIMIT_PATTERNS = (
    r"rate.?limit",
    r"too many requests",
    r"\b429\b",
    r"quota",
    r"insufficient (?:credit|credits|balance|funds|quota)",
    r"credit balance",
    r"out of credits",
    r"no credits",
    r"exceeded your",
    r"usage limit",
    r"limit (?:has been )?(?:reached|exceeded)",
    r"monthly limit",
    r"daily limit",
)
_LIMIT = re.compile("|".join(_LIMIT_PATTERNS), re.IGNORECASE)

# Providers also report a temporary overload; continuing locally is better than
# ending the turn. It is not a quota problem, so it gets its own marker list.
_OVERLOAD_PATTERNS = (
    r"overloaded",
    r"service unavailable",
    r"\b503\b",
)
_OVERLOAD = re.compile("|".join(_OVERLOAD_PATTERNS), re.IGNORECASE)


def is_limit_error(message: str | None) -> bool:
    """True when replaying the prompt elsewhere is likely to work."""
    text = str(message or "")
    return bool(_LIMIT.search(text) or _OVERLOAD.search(text))


def parse_ref(value: str | None) -> dict | None:
    """Turn ``provider/model`` into the model reference the API expects."""
    raw = str(value or "").strip()
    if "/" not in raw:
        return None
    provider, model_id = raw.split("/", 1)
    provider, model_id = provider.strip(), model_id.strip()
    if not provider or not model_id:
        return None
    return {"id": model_id, "providerID": provider}


def fallback_model() -> dict | None:
    """The local model used while the primary one is limited (None = off)."""
    return parse_ref(settings.OPENCODE_FALLBACK_MODEL)


def enabled() -> bool:
    return fallback_model() is not None


def same_model(left: dict | None, right: dict | None) -> bool:
    if not left or not right:
        return False
    return (left.get("providerID") == right.get("providerID")
            and (left.get("id") or left.get("modelID")) == (right.get("id") or right.get("modelID")))


class Cooldown:
    """Remember for how long trying the primary model again is pointless."""

    def __init__(self) -> None:
        self._until = 0.0
        self._reason = ""

    def trigger(self, reason: str = "") -> None:
        seconds = max(0, int(settings.OPENCODE_FALLBACK_COOLDOWN))
        self._until = time.monotonic() + seconds
        self._reason = str(reason or "")[:300]

    def active(self) -> bool:
        return time.monotonic() < self._until

    def clear(self) -> None:
        self._until = 0.0
        self._reason = ""

    def state(self) -> dict:
        remaining = max(0, int(self._until - time.monotonic()))
        return {
            "enabled": enabled(),
            "model": settings.OPENCODE_FALLBACK_MODEL.strip() or None,
            "cooldown": int(settings.OPENCODE_FALLBACK_COOLDOWN),
            "remaining": remaining,
            "active": remaining > 0,
        }


policy = Cooldown()
