# AI copy for Tamil Budget Finds

- `MEESHO_AI_COPY=true` (default) uses local Ollama `gemma3:4b` for the hook,
  three benefit lines, one caution and the CTA.
- Set `MEESHO_AI_COPY=false` in `.env` to force the deterministic template.
- The model sees only the product record: title, price, MRP, rating, orders,
  features and cautions. It is told not to invent claims, numbers or urgency.
- Validation: JSON schema, Tamil-script checks, banned-claim checks and
  new-number checks. Unsafe lines are replaced with catalogue facts. If the
  whole call fails, the deterministic template is used.
- Cold call is about 150 seconds; a warm call is about 20-30 seconds. The model
  stays loaded for 15 minutes.
- `gemma4:12b` is installed but timed out at 240 seconds on this CPU. Keep
  `gemma3:4b` unless a GPU is available.
- The AI does not fetch products, affiliate links or commissions. A real Meesho
  affiliate CSV/API feed is still required for real earnings.
