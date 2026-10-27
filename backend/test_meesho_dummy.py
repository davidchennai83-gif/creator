"""Render one Tamil Budget Finds demo video for the end-to-end upload test."""
import json
import sys
import time
from datetime import date
from pathlib import Path
from uuid import UUID

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.video_creator import jobs

OWNER = UUID("32d9493f-25d2-4928-bf98-3b3360015b94")
DAY = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
LOG = Path("storage") / "finds" / "dummy-render.log"


def write(message):
    stamp = time.strftime("%H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


active = [job for job in jobs.listing(OWNER) if job.get("status") in ("writing", "rendering")]
if active:
    write(f"Refusing to start: another video job is active ({active[0]['id']})")
    raise SystemExit(1)

existing = [job for job in jobs.listing(OWNER)
            if job.get("kind") == "meesho" and job.get("date") == DAY.isoformat()
            and job.get("status") == "complete"]
if existing:
    job = existing[0]
    write(f"Using existing complete job {job['id']}")
else:
    write(f"Creating meesho job for {DAY.isoformat()}")
    job = jobs.new(OWNER, DAY, "ta-IN-PallaviNeural", "meesho", auto_render=True)
    write(f"Job id {job['id']}")

last = None
while True:
    current = jobs.get(job["id"], OWNER)
    if not current:
        write("Job disappeared")
        raise SystemExit(1)
    message = f"{current.get('status')} · {current.get('message')}"
    if message != last:
        write(message)
        last = message
    if current.get("status") in ("complete", "failed"):
        folder = jobs.root() / job["id"]
        write(f"Final status: {current.get('status')}")
        write(f"Folder: {folder}")
        for path in sorted(folder.glob("*.mp4")):
            write(f"MP4: {path} ({path.stat().st_size} bytes)")
        (LOG.parent / "dummy-job.json").write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(0 if current.get("status") == "complete" else 2)
    time.sleep(5)
