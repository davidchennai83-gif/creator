# Kids Learning — Daily 3

Tenth video kind (`kids`). Fully offline and deterministic — no Ollama and no internet.

- `catalog.json`: 36 simple, family-safe items a young child can follow — the twelve Tamil vowels
  (உயிர் எழுத்து), the counting words ஒன்று–எட்டு, common animals (விலங்குகள்) and basic colours
  (நிறங்கள்). Each item has four narration lines: the topic, a plain statement, one concrete
  example, and the closing line "குழந்தைகள் தினமும் ஒன்று கற்போம்."
- Three items a day (`PER_EDITION = 3`), selected by `daily_catalog.py`. The daily line-up never
  repeats for **7,140 days** (C(36,3)).
- Keep it accurate and gentle: only well-known words, no digits in the narration (write numbers as
  words so the Tamil voice reads them), no scary or divisive content.
- `topic` is `education` (letters/numbers/colours) or `globe` (animals) — both already exist in
  `backgrounds.py`, with a per-item Pexels `photo` query in `stock_photos.py`.

Edit `catalog.json` to change wording or add items; more items only lengthens the cycle. This show
is scheduled daily and is included in the upload automation `KINDS`, so it is posted automatically.
