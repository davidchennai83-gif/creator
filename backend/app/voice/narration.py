"""Auto-narration verification.

Every rendered video is built with Tamil narration (edge-tts) mixed into the MP4.
This helper double-checks the finished files really carry an audio stream and
reports the day's videos, so the surveillance agent can shout if one is silent.
"""
import json
import logging
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

from app.config.settings import settings
from .tts import ffmpeg_exe

log = logging.getLogger(__name__)


def _video_root() -> Path:
    return Path(settings.STORAGE_PATH) / "video_creator"


def has_audio(video_path) -> bool:
    """True when the MP4 carries at least one audio stream (parsed from ffmpeg -i)."""
    try:
        result = subprocess.run([ffmpeg_exe(), "-i", str(video_path)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as exc:
        log.warning("ffmpeg probe failed for %s: %s", video_path, exc)
        return False
    banner = (result.stderr or "") + (result.stdout or "")
    return "Audio:" in banner


def _jobs() -> list[dict]:
    db_path = _video_root() / "jobs.sqlite3"
    if not db_path.is_file():
        return []
    out = []
    try:
        with sqlite3.connect(str(db_path), timeout=30) as db:
            for (body,) in db.execute("SELECT body FROM jobs").fetchall():
                try:
                    out.append(json.loads(body))
                except Exception:
                    continue
    except Exception as exc:
        log.warning("could not read jobs db: %s", exc)
    return out


def day_videos(day=None) -> list[dict]:
    """Today's video jobs with narration status for each finished MP4."""
    day = day or date.today().isoformat()
    videos = []
    for job in _jobs():
        if job.get("date") != day:
            continue
        folder = _video_root() / job["id"]
        mp4s = sorted(folder.glob("*.mp4")) if folder.is_dir() else []
        narrated = [p for p in mp4s if has_audio(p)]
        videos.append({
            "id": job["id"],
            "kind": job.get("kind", "history"),
            "status": job.get("status"),
            "message": job.get("message", ""),
            "files": [p.name for p in mp4s],
            "has_narration": bool(mp4s) and len(narrated) == len(mp4s),
            "narrated_files": len(narrated),
        })
    videos.sort(key=lambda v: v["kind"])
    return videos
