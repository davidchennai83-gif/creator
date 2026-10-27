"""On-disk storage for recorder scripts.

Layout: <RECORDINGS_PATH>/<record_type>/<name>.py  where record_type is 'web' or
'desktop'. The two buckets mirror the recorder page's record type so a browser
recording and a desktop recording never overwrite each other.

Every name is sanitised and the resolved path is asserted to stay inside the
recordings root, so a hostile name like '../../app.py' cannot escape.
"""
import os
import re
from datetime import datetime
from pathlib import Path

from app.config.settings import settings

RECORD_TYPES = ("web", "desktop")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")


def root() -> Path:
    return Path(settings.RECORDINGS_PATH)


def safe_name(name: str) -> str:
    """Reduce an arbitrary name to a single safe path component ending in .py."""
    cleaned = _SAFE_NAME.sub("_", (name or "").strip()).strip("._")
    if not cleaned:
        cleaned = "untitled"
    if not cleaned.lower().endswith(".py"):
        cleaned = f"{cleaned}.py"
    return cleaned[:180]


def safe_type(record_type: str) -> str:
    return record_type if record_type in RECORD_TYPES else "web"


def folder(record_type: str) -> Path:
    return root() / safe_type(record_type)


def path_for(name: str, record_type: str) -> Path:
    """Absolute path for a recording, guaranteed to live under the root."""
    base = folder(record_type).resolve()
    target = (base / safe_name(name)).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Invalid recording name")
    return target


def find(name: str) -> tuple[Path, str] | None:
    """Locate a recording in either bucket. Returns (path, record_type)."""
    for record_type in RECORD_TYPES:
        candidate = path_for(name, record_type)
        if candidate.is_file():
            return candidate, record_type
    return None


def listing() -> list[dict]:
    result = []
    for record_type in RECORD_TYPES:
        directory = folder(record_type)
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir(), key=lambda p: p.name, reverse=True):
            if not entry.is_file() or entry.suffix != ".py":
                continue
            stat = entry.stat()
            result.append(
                {
                    "name": entry.name,
                    "type": record_type,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return result


def read(name: str) -> dict | None:
    found = find(name)
    if not found:
        return None
    path, record_type = found
    return {
        "name": path.name,
        "type": record_type,
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def write(name: str, record_type: str, content: str) -> str:
    path = path_for(name, record_type)
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")
    return path.name


def delete(name: str) -> bool:
    found = find(name)
    if not found:
        return False
    path, _ = found
    try:
        path.unlink()
        return True
    except OSError:
        return False
