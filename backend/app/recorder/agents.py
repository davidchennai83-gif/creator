"""Registry of connected local recorder agents, keyed by their Socket.IO sid."""
import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_agents: dict[str, dict] = {}


def register(sid: str, info: dict) -> dict:
    record = {
        "sid": sid,
        "version": info.get("version"),
        "platform": info.get("platform"),
        "hostname": info.get("hostname") or "unknown",
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _agents[sid] = record
    return record


def unregister(sid: str) -> bool:
    with _lock:
        return _agents.pop(sid, None) is not None


def all_agents() -> list[dict]:
    with _lock:
        return list(_agents.values())


def count() -> int:
    with _lock:
        return len(_agents)


def resolve_sid(sid: str | None) -> str | None:
    """Return the requested sid when it is a live agent. A stale sid is never
    silently redirected to another machine; with no sid given (single-agent
    setups) the oldest connected agent is used."""
    with _lock:
        if sid:
            return sid if sid in _agents else None
        if _agents:
            return next(iter(_agents))
        return None
