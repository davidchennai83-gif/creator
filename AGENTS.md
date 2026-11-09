# Agent guide - creator-platform

This repository runs a personal video pipeline: it renders Tamil videos, then
publishes them to YouTube, Facebook and Instagram through a logged-in Chrome
profile. Most requests reach the agent from a phone through Tailscale, so keep
answers short and never expose raw errors.

## Answering status / schedule questions first

Questions such as "Inniku videos enna time ku generate aagum?" or "Did the
uploads finish?" must NOT trigger codebase exploration. Run exactly one command
from the repository root:

```powershell
python scripts/today_status.py
```

Add `--short` for a compact answer, or `--date YYYY-MM-DD` for another day.
The script reads the two SQLite stores and prints ASCII only, so it is safe on
the cp1252 console.

Then reply in Tanglish (the user's language), for example:

> Inniku 11:00 ku YouTube upload start aagum. Renders: 3/11 done, history ippo
> render aaguthu. Next video kids 08:40.

Rules:
- One tool call is usually enough. Do not search the codebase, read source
  files, or inspect logs for a simple status question.
- Never paste a Python traceback, stack trace, or raw exception into the reply.
  Translate it into one plain sentence.
- If the script itself fails, say "status file open aagala" and give the one
  relevant reason. Do not fall back to a long shell investigation.
- Do not print Tamil to a Windows console without setting
  `$env:PYTHONIOENCODING="utf-8"`; the default code page is cp1252 and printing
  Tamil raises `UnicodeEncodeError`.

## Useful paths (run from the repo root)

- Render schedule: `backend/storage/video_creator/schedules.sqlite3`
- Render jobs: `backend/storage/video_creator/jobs.sqlite3`
- Backend log: `backend/storage/web-server.log`
- OpenCode server log: `backend/storage/logs/opencode-server.log`
- Upload automation: `backend/storage/automation/projects/* Upload/main.py`

Both SQLite files store one JSON document per row in a `body` column; there is
no `date`, `status` or `project` column. Use `scripts/today_status.py` instead
of writing ad-hoc SQL.

## Pipeline facts

- Daily render schedule (Asia/Kolkata): news 05:30, health 05:50, motivation
  06:10, history 08:00, indian-law 08:05, make-money 08:20, kids 08:40,
  thirukkural 09:00, english 09:20, gk 09:40, meesho 19:00.
- Uploads: YouTube 11:00, Facebook 15:30, Instagram 15:45. Meesho uploads at
  19:20 / 19:45 / 20:00.
- Every YouTube upload is cross-posted to Facebook and Instagram. Descriptions
  include the YouTube link with `?sub_confirmation=1`.
- Upload automation drives the already signed-in Chrome profile
  (`CreatorRecorder`, CDP port 9222). Never open a second browser window and
  never use Playwright `set_input_files`; push files through CDP
  `DOM.setFileInputFiles` and suppress native file dialogs.
- Only one Playwright client can hold Chrome 9222 at a time. YouTube connects
  per video and releases the connection before the social uploads run.
- Optional AI video: Wan 2.2 TI2V-5B lives in an isolated install
  (`D:\ai\ComfyUI`, venv `D:\ai\venv-wan`, started with
  `D:\ai\run_comfy.ps1` on port 8188). Measured here: ~25 min for a 49 frame
  2 s clip at 480x832 including the cold model load, and it holds ~6 GB VRAM.
  So `VIDEO_WAN=false` by default, `WAN_KINDS=history` keeps it to one render,
  and `WAN_TIMEOUT` caps a stuck job before the video falls back to motion.
  Never start it while an upload is running: it needs ~6 GB VRAM and a lot of
  RAM.
- Encoder: `h264_nvenc` (p7, `VIDEO_CQ`) with automatic `libx264` fallback.
  `VIDEO_FPS=30`, output is limited-range BT.709, audio 48 kHz.

## Development commands

- Frontend build: `cd frontend` then `npm run build` (use `cmd /c npm ...` if
  PowerShell blocks the shim).
- Backend: Hypercorn on `127.0.0.1:8000`, served by `backend/supervise.py`.
  Restart it after Python changes; there is no reloader.
- Type check: `cd frontend` then `npx tsc --noEmit`.

## Safety

- Do not delete jobs, schedules, rendered media, or sessions unless the user
  explicitly asks.
- Do not commit `.env`, credentials, tokens, or browser profile data.
- Destructive shell commands and bulk file changes need explicit confirmation.
