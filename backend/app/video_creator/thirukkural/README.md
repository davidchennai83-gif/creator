# Thirukkural — Daily 2 Couplets

Fifth video kind (`thirukkural`) next to Day of History, Indian Law, How to Make Money and the
daily Tamil news. This one is **fully offline and deterministic** — no Ollama and no internet
at render time.

- `catalog.json`: 1,080 kurals — the Virtue (அறத்துப்பால்) and Wealth (பொருட்பால்) sections,
  kurals 1–1080 — built once by `scripts/build_thirukkural_catalog.py` from the public-domain
  Project Madurai text. The love section (kurals 1081–1330) is intentionally excluded so the
  channel stays family friendly; change `MAX_KURAL` in the build script to include it.
- Every item carries its own `lines`: the Tamil couplet (two lines) followed by Mu. Varadarajan's
  standard Tamil explanation, wrapped to ≤150 characters so the on-screen font stays readable.
  Digits are stripped because the narration voice reads them unpredictably (write numbers as words).
- Two couplets a day (`PER_EDITION = 2`), selected by the shared combination engine in
  `daily_catalog.py`. The daily pair never repeats for **582,660 days**.
- Voice and narration are identical to the other kinds: the lines are joined with `'. '` and spoken
  with the chosen Tamil edge-tts voice.

Rebuild the catalogue from scratch:

    python scripts/build_thirukkural_catalog.py RAW_JSON \
        backend/app/video_creator/thirukkural/catalog.json
