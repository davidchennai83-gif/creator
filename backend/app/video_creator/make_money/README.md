# How to Make Money — Daily 5 Ideas

Third video kind (`make-money`) next to Day of History and Indian Law. Same flow: generate script,
review, render, download. No Ollama needed.

- `catalog.json`: 30 practical ideas. Each has an English title, Tamil title, icon `topic`, Pexels `photo`
  query, four English reference facts (for review) and official links where they matter (FSSAI, SEBI, RBI, cybercrime.gov.in).
- `tamil.json`: four standard written-Tamil lines per idea (hook, first step, what you need, caution),
  in the same formal register as the Day of History narration. **Edit this file to change wording.**
  Keep each line under 110 characters and avoid digits (the voice reads them unpredictably; write
  numbers as words, e.g. "ஐம்பது சதவீதம்" not "50%").
- The date picks five ideas (`daily_ideas`); consecutive days never overlap and the cycle repeats every 6 days.
  Each cycle day has a theme: skills, teaching, content, food/craft, gig work, money habits + scam alerts.
- Voice and narration: identical path to Day of History and Indian Law — the four lines are joined with
  `'. '` and sent to the same `speech()` call with the voice the user picked (Pallavi / Valluvar), no
  per-kind rate or pitch tuning.
- Content is educational, not financial advice, and never promises income. Keep it that way when adding ideas.

Smoke test with real speech and video (from `backend`):

```powershell
.\.venv\Scripts\python.exe ..\scripts\check_history_pipeline.py --kind make-money --render
```
