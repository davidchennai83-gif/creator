# Spoken English — Daily Phrases

Sixth video kind (`english`). Fully offline and deterministic — no Ollama and no internet.

- `catalog.json`: 20 practical everyday English phrases (greetings, courtesy, introductions, small
  talk, shopping, asking for help, parting). Each item has four Tamil narration lines: the phrase,
  its Tamil meaning, an example sentence, and a closing tip. Every line keeps a Tamil word so the
  Tamil narration voice reads the English phrase the way a spoken-English class for Tamil learners
  sounds.
- Three phrases a day (`PER_EDITION = 3`), selected by `daily_catalog.py`. The daily line-up never
  repeats for **1,140 days** (C(20,3)).
- Edit `catalog.json` to change wording or add phrases. More items only lengthens the cycle; the
  project refuses to run if the cycle would be shorter than 365 days.

Adding a phrase: copy any item, give it a unique `id`, a `theme`, a `topic` of `chat` (or another
icon in `backgrounds.py`), a Pexels `photo` query, four `lines` (each with Tamil script, ≤150 chars)
and English `facts` for the review panel.
