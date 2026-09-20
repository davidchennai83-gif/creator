# Indian Law — Daily 5 Acts

The Video Creator card uses curated Tamil explanations, Tamil neural speech,
Chromium Tamil text shaping and MP4/BGM renderer.

- `catalog.json`: 15 introductory central Acts with four reference facts each and
  section citations. India Code lookup links accompany each generated explanation.
- The selected date determines five distinct Acts. Adjacent days have different
  sets; this initial catalog repeats after three days. Add catalog entries to expand coverage.
- `tamil.json` contains four Tamil explanations per Act, avoiding unreliable
  local-model translation of legal terms. Ollama remains in use for History.
  Each edition contains five source IDs exactly once. Script review, voice
  selection, progress, saved jobs and authenticated download match History.
- Daily creation is **button-triggered**, like History; no unattended schedule is installed.
- The catalog is a general educational overview, not a live retrieval of amendments,
  state-specific rules or legal advice. Source links are Act lookup links, not claims
  that official text was fetched at generation time.

Run a real script/speech/video test from `backend`:

```powershell
.\.venv\Scripts\python.exe ..\scripts\check_history_pipeline.py --kind indian-law --render
```

Artifacts remain in the isolated smoke-test folder printed by the command.
