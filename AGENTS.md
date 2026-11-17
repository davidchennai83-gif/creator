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
  thirukkural 09:00, english 09:20, gk 09:40, cinema 09:55, meesho 19:00.
- Uploads: YouTube 11:00, Facebook 15:30, Instagram 15:45. Meesho uploads at
  19:20 / 19:45 / 20:00. The YouTube run uploads `news` first, then `cinema`,
  then the rest, so the two time-sensitive bulletins never lose the race.
- Two bulletins share one engine: `news/__init__.py` holds the RSS parsing,
  duplicate detection, attribution and narration, and a `Profile` only names
  what differs (feeds, filters, caps, labels). `cinema/__init__.py` is that
  profile (`PROFILE`) plus `create_script`. A new bulletin edition means a new
  profile, never a copy of the engine.
- Cinema bulletin sources: Ananda Vikatan's cinema desk (`SHOWBIZ` filter, it
  also republishes the day's general trending story), Sathiyam TV cinema, and
  the general newsroom feeds read through `FILM_STORY`. The filter looks at the
  headline and section only, because a general feed's body copy often name-drops
  a film. Feeds with no usable text (hashtag-only captions) still run, but the
  selection prefers stories it can actually narrate.
- A bulletin scene keeps the publisher's own photo of that story (`provider`
  `feed`); real footage only fills scenes whose feed image could not be
  downloaded. `stock_video.prepare(..., skip=...)` is how that is enforced.
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
- Real footage backgrounds: `VIDEO_SOURCE=stock` replaces the Ken Burns photo
  with a portrait video clip per scene (`stock_video.py`), Pexels first and
  Pixabay when Pexels has no fresh match. Search words come from the point's
  own `photo_query`, else the local Ollama model turns the item's English title
  into a "what the camera sees" phrase (cached per text), else a kind preset.
  Guards keep footage on-topic: a result must share a meaningful word with its
  own Pexels slug / Pixabay tags, animated and motion-graphic clips are refused,
  and a visual adjective alone ("glowing") never counts as a match. Anything
  else keeps its photo animation, so a source outage never fails a render.
- Backgrounds never repeat: `fresh.py` records every photo/video id in
  `storage/video_creator/used-media.json` and the pickers skip ids used inside
  `STOCK_REUSE_DAYS` (21). The first run seeds the file from past jobs'
  `media_sources`, so yesterday's pictures are not shown again.
- Photo sources, in order: Pexels -> Pixabay -> Unsplash -> Openverse ->
  Wikimedia Commons. Pexels / Pixabay keys and the Unsplash key live in
  `backend/.env`; a source with no key is simply skipped. Commons and Openverse
  need no key, so the pipeline still gets fresh, on-topic photos without one.
  Commons is tried last but is the most literal: it is a library, so "palm leaf
  manuscript" returns the actual object rather than a lookalike stock photo.
  Only CC0 / public domain / plain CC BY are accepted (NC, ND and BY-SA refused
  because the videos are monetised and cropped). Every provider's own label
  (Pexels alt, Pixabay tags, Unsplash alt, Commons file name) must name
  something in the query; an unlabelled photo is accepted as unknown, a
  contradicting label is rejected in favour of the topic illustration.
- Meesho stays on product photos and news stays on its publisher image
  (`STOCK_SKIP_KINDS`). Cinema news is not in that list: its publisher photo is
  used when it exists, and the footage search covers the scenes without one.
  Clips are cached by Pexels id under `storage/video_creator/pexels-cache` and
  pruned past 8 GB.
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
