# Health Tips — Daily 3

Eighth video kind (`health`). Fully offline and deterministic — no Ollama and no internet.

- `catalog.json`: 20 simple, widely accepted everyday wellbeing tips — hydration, sleep, movement,
  diet, hygiene, posture, eyes, mind and prevention — written in spoken Tamil. Each item has four
  narration lines.
- Three tips a day (`PER_EDITION = 3`), selected by `daily_catalog.py`. The daily line-up never
  repeats for **1,140 days** (C(20,3)).
- Keep the advice safe and general: no diagnosis, no medicine names, no dosages, no cures. If you
  add tips, stick to everyday lifestyle habits and always recommend seeing a doctor for problems.
- `topic` is `health` (icon in `backgrounds.py`), with a per-item Pexels `photo` query.

Edit `catalog.json` to change tips or add more; more items only lengthens the cycle.
