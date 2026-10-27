# Amazing Facts — Daily GK

Seventh video kind (`gk`). Fully offline and deterministic — no Ollama and no internet.

- `catalog.json`: 20 evergreen, checkable general-knowledge facts (human body, animals, space,
  science, food, earth) written in simple spoken Tamil. Each item has four narration lines: the
  topic, two fact lines, and a closing invitation.
- Three facts a day (`PER_EDITION = 3`), selected by `daily_catalog.py`. The daily line-up never
  repeats for **1,140 days** (C(20,3)).
- Facts are things that do not go out of date. Avoid anything political, medical-advice or
  contested; keep it family friendly and verifiable.
- `topic` is `globe` (icon in `backgrounds.py`), with a per-item Pexels `photo` query.

Edit `catalog.json` to change facts or add more; more items only lengthens the cycle.
