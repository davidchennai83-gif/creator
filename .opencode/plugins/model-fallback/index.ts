import { Plugin } from "@opencode/plugin"

/**
 * Automatic model fallback for the coding agent.
 *
 * OpenCode ends a turn when a provider reports a rate limit, an exhausted
 * quota or a spent credit balance. This plugin keeps the session usable:
 *
 *   1. the failure starts a cooldown and switches the session to a local
 *      Ollama model, and the retry runs there;
 *   2. while the cooldown lasts, every new prompt is sent to the local model;
 *   3. once the cooldown expires the next prompt goes back to the primary
 *      model, so a recovered quota is used again without any manual switch.
 *
 * The web chat implements the same policy in the backend, because it streams
 * the retry itself; this plugin covers the terminal and desktop clients.
 */

const LIMIT =
  /rate.?limit|too many requests|\b429\b|quota|insufficient (?:credit|credits|balance|funds|quota)|credit balance|out of credits|no credits|exceeded your|usage limit|limit (?:has been )?(?:reached|exceeded)|monthly limit|daily limit|overloaded|service unavailable|\b503\b/i

const DEFAULT_PRIMARY = "opencode/deepseek-v4.1-flash-free"
const DEFAULT_FALLBACK = "ollama/qwen2.5-coder:7b"
const DEFAULT_COOLDOWN = 600

interface Ref {
  providerID: string
  id: string
}

function parseRef(value: unknown): Ref | undefined {
  const raw = String(value ?? "").trim()
  const slash = raw.indexOf("/")
  if (slash <= 0 || slash === raw.length - 1) return undefined
  return { providerID: raw.slice(0, slash), id: raw.slice(slash + 1) }
}

function sameRef(left: Ref | undefined, right: Ref | undefined): boolean {
  return Boolean(left && right && left.providerID === right.providerID && left.id === right.id)
}

function isLimit(message: unknown, status?: number): boolean {
  return status === 429 || LIMIT.test(String(message ?? ""))
}

export default Plugin.define({
  id: "creator.model-fallback",
  async setup(ctx) {
    const primary =
      parseRef(ctx.options.primary) ?? parseRef(process.env.CREATOR_PRIMARY_MODEL) ?? parseRef(DEFAULT_PRIMARY)
    const fallback =
      parseRef(ctx.options.fallback) ?? parseRef(process.env.CREATOR_FALLBACK_MODEL) ?? parseRef(DEFAULT_FALLBACK)
    // Minutes would be too coarse and milliseconds too easy to typo, so the
    // option is seconds like the backend setting.
    const cooldown = Math.max(30, Number(ctx.options.cooldown ?? process.env.CREATOR_FALLBACK_COOLDOWN) || DEFAULT_COOLDOWN) * 1000
    if (!primary || !fallback) return

    let limitedUntil = 0
    const cooling = () => Date.now() < limitedUntil
    // Only sessions this plugin moved are moved back; a user who deliberately
    // picked a local model keeps it.
    const moved = new Set<string>()

    const switchTo = async (sessionID: string, model: Ref): Promise<boolean> => {
      try {
        await ctx.session.switchModel({ sessionID, model })
        return true
      } catch {
        return false
      }
    }

    const moveToFallback = async (sessionID: string): Promise<void> => {
      if (await switchTo(sessionID, fallback)) moved.add(sessionID)
    }

    const modelOf = async (sessionID: string): Promise<Ref | undefined> => {
      try {
        const session = (await ctx.session.get({ sessionID })) as
          | { model?: { providerID: string; id: string }; data?: { model?: { providerID: string; id: string } } }
          | undefined
        const model = session?.model ?? session?.data?.model
        return model ? { providerID: model.providerID, id: model.id } : undefined
      } catch {
        return undefined
      }
    }

    await ctx.session.hook("prompt", async (event) => {
      const current = await modelOf(event.sessionID)
      // Never guess: a session on some other provider (Gemini, a second local
      // model, ...) must stay exactly where the user put it.
      if (!current) return
      if (!cooling()) {
        // Quota window is over: go back and find out whether it recovered.
        if (moved.has(event.sessionID)) {
          if (await switchTo(event.sessionID, primary)) moved.delete(event.sessionID)
        }
        return
      }
      if (sameRef(current, primary)) await moveToFallback(event.sessionID)
    })

    await ctx.session.hook("retry", async (event) => {
      if (!isLimit(event.error?.message, event.error?.status)) return
      if (sameRef(event.model, fallback)) return
      limitedUntil = Date.now() + cooldown
      await moveToFallback(event.sessionID)
      // Let OpenCode try again; it re-reads the session model for the attempt.
      event.decision = { retry: true, delay: 1500 }
    })

    // Backup for clients that do not retry: the next prompt goes local.
    const controller = new AbortController()
    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({
          types: ["session.execution.failed"],
          signal: controller.signal,
        })) {
          const data = (event as { data?: { sessionID?: string; error?: unknown } }).data ?? {}
          const error = data.error
          const message =
            typeof error === "string" ? error : (error as { message?: string } | undefined)?.message ?? ""
          const status = typeof error === "object" && error ? (error as { status?: number }).status : undefined
          if (!data.sessionID || !isLimit(message, status)) continue
          limitedUntil = Date.now() + cooldown
          await moveToFallback(data.sessionID)
        }
      } catch {
        /* Plugin unloaded or the event stream closed. */
      }
    })()

    return () => controller.abort()
  },
})
