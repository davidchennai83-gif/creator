# CreatorMart — 365-Day Video Content Plan

Goal: the Video Creator can produce a **fresh daily video for a full year (and much longer)
without repeating a day, without internet and without loading the CPU** — so the machine keeps
running and never chokes.

## The engine: `backend/app/video_creator/daily_catalog.py`

Every "catalogue" show ships a `catalog.json` (a list of items) and gets a `create_script` for
free from `make_creator(folder, per_day)`. Each day the engine picks `per_day` **distinct** items.

It does **not** slice a contiguous block (the old kinds did that, which is why `make-money` — 30
ideas, 5 a day — repeats every 6 days). Instead it strides through the space of all `k`-combinations
(combinadic unranking) with a step coprime to that size. So:

- the cycle length is `C(n, k)` days — astronomically large even for a small catalogue, and
- consecutive days share almost no items, so the rundown feels genuinely different.

`cycle_days(n, k)` reports the figure, and `make_creator` **refuses to run** if a show would cover
fewer than 365 days. That guarantee is automatic for every current and future catalogue show.

## Shows and coverage

| Show | Kind | Items | Per day | Fresh for | Needs |
|------|------|-------|---------|-----------|-------|
| Day of History | `history` | live sources | 10 | daily (LLM) | Ollama + internet |
| Indian Law — Daily 5 Acts | `indian-law` | 15 | 5 | 3 days | offline |
| How to Make Money | `make-money` | 30 | 5 | 6 days | offline |
| Daily News — 10 Tamil stories | `news` | live RSS feeds | 10 | daily | internet |
| **Thirukkural — Daily 2 Couplets** | `thirukkural` | 1,080 | 2 | **582,660 days** | offline (bundled text) |
| **Spoken English — Daily Phrases** | `english` | 20 | 3 | **1,140 days** | offline |
| **Amazing Facts — Daily GK** | `gk` | 20 | 3 | **1,140 days** | offline |
| **Health Tips — Daily 3** | `health` | 20 | 3 | **1,140 days** | offline |
| **Life Lessons — Daily 3** | `motivation` | 20 | 3 | **1,140 days** | offline |
| **Kids Learning — Daily 3** | `kids` | 36 | 3 | **7,140 days** | offline |

The six bold shows are fully deterministic and offline: no language model, no network download,
no CPU cost beyond normal speech + render. That is what makes a 365-day run safe on one PC.

## Daily schedule (Asia/Kolkata)

Seven video renders are scheduled daily, staggered so the render gate runs them one at a time, plus
the three social uploads:

| Time | Task |
|------|------|
| 08:00 | history (LLM) |
| 08:05 | indian-law |
| 08:20 | make-money |
| 08:40 | kids |
| 09:00 | thirukkural |
| 09:20 | english |
| 09:40 | gk |
| 10:00 | YouTube upload |
| 10:15 | Facebook upload |
| 10:30 | Instagram upload |

`health` and `motivation` are **built and selectable but not scheduled**, so they add zero render
load until you enable them in the Scheduler. All tasks run to **2036-09-01**.

> The render gate allows only one render at a time, so the seven are never concurrent. If a render
> overruns, later ones wait their turn (the job shows "waiting for the current video to finish").

### Publishing (YouTube / Facebook / Instagram)

The three upload projects read one shared `content.py` (`storage/automation/projects/*/content.py`).
It lists every kind it will post in `KINDS` and holds the per-kind title/tags in `KIND_META`.
**All ten kinds are listed**, so every show that renders is uploaded automatically; a kind with no
finished video that day is simply skipped. Each uploader runs `main.py` with no arguments, which
posts today (and yesterday, as a catch-up) and records each file in its `*_uploaded.log` so nothing
is posted twice. Add a new show to `KINDS` + `KIND_META` when you add it to the Video Creator.

## Adding a new show (5 minutes, no model)

1. Make `backend/app/video_creator/<name>/`.
2. Write `catalog.json`: items with `id`, `theme`, `title`, `title_en`, `topic`, `photo`,
   `lines` (Tamil narration, ≤150 chars each, must contain Tamil script, no bare digits) and
   `facts` (English, shown in the review panel).
3. Add `__init__.py`:
   ```python
   from pathlib import Path
   from ..daily_catalog import make_creator
   create_script = make_creator(Path(__file__).parent, PER_EDITION)
   ```
4. Register the kind in `registry.py` (`_CREATORS`), `routes.py` (kind `Literal` + download
   prefix), `schedules.py` (`PROJECTS`), and the frontend `KINDS` + buttons + `KIND_LABEL`.
5. Use a `topic` that already exists in `backgrounds.py`/`stock_photos.py`, or add an icon.

## Why this is safe for the machine

- No per-day model call for the new shows (only `history` uses Ollama).
- Renders are serialised by the render gate; the seven daily jobs spread across two hours.
- Catalogues are read-only JSON, cached in memory.
- The autonomous self-upgrade (`UPGRADES.md`) can keep enriching catalogues and adding shows
  without touching the pipeline.

## Roadmap

- Grow each 20-item catalogue toward 60+ (still only ~1,140 → 34,220-day cycles) for more variety.
- Per-kind YouTube **titles, descriptions and tags** so uploads read naturally.
- Auto **thumbnail** variants per show.
- Optional Tamil/English label toggle and voice per show.
- Enable `health` / `motivation` in the Scheduler when the render budget allows.
