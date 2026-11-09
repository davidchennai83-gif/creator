import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Loader2, Plus, Send, Square, X } from 'lucide-react';
import clsx from 'clsx';
import {
  ChatMessage,
  AgentModel,
  ModelRef,
  opencodeService,
  streamReply,
} from '../services/opencode';

const STORAGE_KEY = 'creator-opencode-chat-v1';

interface StoredChat {
  sessionId: string | null;
  model: ModelRef | null;
  messages: ChatMessage[];
}

function readStored(): StoredChat {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { sessionId: null, model: null, messages: [] };
    const parsed = JSON.parse(raw) as Partial<StoredChat>;
    return {
      sessionId: parsed.sessionId || null,
      model: parsed.model || null,
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
    };
  } catch {
    return { sessionId: null, model: null, messages: [] };
  }
}

const starterPrompts = [
  'Summarise today\'s upload status.',
  'Why did the Instagram upload fail?',
  'Improve the Video Creator page.',
];

/** Small markdown-ish renderer: plain text with **bold**, `code` and fenced blocks. */
function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`\n]+`)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
          return (
            <code key={index} className="rounded bg-gray-100 px-1 py-0.5 text-[0.85em] text-gray-800">
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}

function MessageBody({ text }: { text: string }) {
  const parts = text.split('```');
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <pre
            key={index}
            className="mt-2 max-w-full overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100"
          >
            {part.replace(/^[a-zA-Z0-9+#-]+\n/, '')}
          </pre>
        ) : (
          <span key={index} className="whitespace-pre-wrap break-words"><RichText text={part} /></span>
        ),
      )}
    </>
  );
}

export default function OpenCodeChat({
  variant = 'dock',
  onClose,
}: {
  variant?: 'dock' | 'page';
  onClose?: () => void;
}) {
  const stored = useMemo(readStored, []);
  const [messages, setMessages] = useState<ChatMessage[]>(stored.messages);
  const [input, setInput] = useState('');
  const [models, setModels] = useState<AgentModel[]>([]);
  const [model, setModel] = useState<ModelRef | null>(stored.model);
  const [sessionId, setSessionId] = useState<string | null>(stored.sessionId);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const loadRef = useRef(0);

  const grouped = useMemo(() => {
    const map = new Map<string, AgentModel[]>();
    for (const item of models) {
      const list = map.get(item.providerID) || [];
      list.push(item);
      map.set(item.providerID, list);
    }
    return [...map.entries()];
  }, [models]);

  const selectedValue = model ? `${model.providerID}/${model.id}` : '';

  const load = useCallback(async () => {
    const run = ++loadRef.current;
    setLoading(true);
    setError('');
    try {
      const catalogue = await opencodeService.models();
      if (run !== loadRef.current) return;
      // The backend already drops models without tool support; filter here too
      // so a cached/older server can never leave the dead deepseek-coder-v2
      // entry in the picker.
      const usable = catalogue.models.filter(item => item.tools !== false);
      const preferred = catalogue.default;
      const fallback = preferred && usable.some(
        item => item.id === preferred.id && item.providerID === preferred.providerID,
      ) ? preferred : (usable[0] ? { id: usable[0].id, providerID: usable[0].providerID } : null);
      setModels(usable);
      setModel(previous => {
        const exists = previous && usable.some(
          item => item.id === previous.id && item.providerID === previous.providerID,
        );
        return exists ? previous : fallback;
      });
      const saved = readStored();
      if (saved.sessionId) {
        try {
          const history = await opencodeService.messages(saved.sessionId);
          if (run === loadRef.current && history.length) setMessages(history);
        } catch {
          /* Keep the locally cached transcript if history cannot be read. */
        }
      }
    } catch (err) {
      if (run === loadRef.current) {
        setError(err instanceof Error ? err.message : 'OpenCode is unavailable');
      }
    } finally {
      if (run === loadRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    return () => { loadRef.current += 1; };
  }, [load]);

  // Persist the transcript (debounced: token deltas arrive many times a second).
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const snapshot: StoredChat = { sessionId, model, messages: messages.slice(-200) };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
      } catch {
        /* Storage may be full or disabled; the chat still works in memory. */
      }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [sessionId, model, messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: streaming ? 'auto' : 'smooth', block: 'end' });
  }, [messages, status, streaming]);

  const patchMessage = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages(previous => previous.map(item => (item.id === id ? { ...item, ...patch } : item)));
  }, []);

  const stop = useCallback(async () => {
    const id = sessionId;
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setStatus('');
    if (id) {
      try {
        await opencodeService.interrupt(id);
      } catch {
        /* The run may have already finished. */
      }
    }
  }, [sessionId]);

  async function send(textOverride?: string) {
    const text = (textOverride ?? input).trim();
    if (!text || streaming || !model) return;

    setInput('');
    setError('');
    const replyId = `local-assistant-${Date.now()}`;
    setMessages(previous => [
      ...previous,
      { id: `local-user-${Date.now()}`, role: 'user', text },
      { id: replyId, role: 'assistant', text: '', pending: true },
    ]);
    setStreaming(true);
    setStatus('Connecting to OpenCode…');
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let id = sessionId;
      if (!id) {
        const created = await opencodeService.createSession(model, text.slice(0, 60));
        id = created.id;
        setSessionId(id);
      } else {
        // Repair a session created before the model list was filtered (e.g. it
        // was switched to deepseek-coder-v2, which cannot run the tool-using
        // agent). Setting it here makes every send self-healing.
        try {
          await opencodeService.setModel(id, model);
        } catch {
          /* The prompt below reports an expired session. */
        }
      }

      for await (const event of streamReply(id, text, controller.signal)) {
        switch (event.type) {
          case 'accepted':
          case 'started':
            setStatus('Thinking…');
            break;
          case 'step':
            setStatus(event.agent ? `Working (${event.agent})…` : 'Working…');
            break;
          case 'tool':
            setStatus(`Using ${event.name}…`);
            break;
          case 'tool-done':
            setStatus('Thinking…');
            break;
          case 'notice':
            // The backend moved this turn to a local model (limit / quota).
            // Clear the error it already reported, because the turn continues.
            setError('');
            patchMessage(replyId, { notice: event.message, error: undefined, pending: false });
            break;
          case 'delta':
            setStatus('');
            setMessages(previous => previous.map(item =>
              item.id === replyId ? { ...item, text: item.text + event.text, pending: false } : item,
            ));
            break;
          case 'text-start':
            // A new text block after a tool call: keep the earlier narration.
            setMessages(previous => previous.map(item =>
              item.id === replyId && item.text
                ? { ...item, text: `${item.text.replace(/\s*$/, '')}\n\n`, pending: false }
                : item,
            ));
            break;
          case 'text':
            setMessages(previous => previous.map(item =>
              item.id === replyId && !item.text ? { ...item, text: event.text, pending: false } : item,
            ));
            break;
          case 'error': {
            const expired = /404|not found/i.test(event.message);
            const message = expired
              ? 'This conversation expired on the server. Your next message starts a new one.'
              : event.message;
            setError(message);
            if (expired) setSessionId(null);
            patchMessage(replyId, { pending: false, error: message });
            break;
          }
          case 'interrupted':
            setStatus('Stopped.');
            patchMessage(replyId, { pending: false });
            break;
          case 'done':
            setStatus('');
            patchMessage(replyId, { pending: false });
            break;
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        const message = err instanceof Error ? err.message : 'OpenCode request failed';
        setError(message);
        patchMessage(replyId, { pending: false, error: message });
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setStreaming(false);
      setStatus('');
      setMessages(previous => previous.map(item =>
        item.id === replyId && item.pending
          ? { ...item, pending: false, text: item.text || 'No reply was returned.' }
          : item,
      ));
    }
  }

  function newChat() {
    if (streaming) void stop();
    setSessionId(null);
    setMessages([]);
    setError('');
    setStatus('');
    setInput('');
    composerRef.current?.focus();
  }

  async function changeModel(value: string) {
    const [providerID, ...rest] = value.split('/');
    const id = rest.join('/');
    const picked = models.find(item => item.id === id && item.providerID === providerID);
    if (!picked) return;
    const next: ModelRef = { id: picked.id, providerID: picked.providerID };
    setModel(next);
    if (sessionId) {
      try {
        await opencodeService.setModel(sessionId, next);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not change the model');
      }
    }
  }

  const disabled = streaming || loading || !model;

  return (
    <section
      className={clsx(
        'flex flex-col overflow-hidden bg-white',
        variant === 'dock' ? 'h-full w-full border border-gray-200 shadow-2xl rounded-none sm:rounded-2xl' : 'h-full rounded-2xl border border-gray-200 shadow-sm',
      )}
      aria-label="OpenCode chat"
    >
      <header className="flex items-center gap-3 border-b border-gray-200 bg-dark-900 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] text-white">
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary-600">
          <Bot size={18} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold">OpenCode</h2>
          <p className="truncate text-[11px] text-gray-400">
            {sessionId ? `Session ${sessionId.slice(0, 14)}…` : 'New conversation'}
          </p>
        </div>
        <button
          type="button"
          onClick={newChat}
          title="New chat"
          className="rounded-md p-2 text-gray-300 hover:bg-dark-800 hover:text-white"
        >
          <Plus size={18} aria-hidden="true" />
          <span className="sr-only">New chat</span>
        </button>
        {variant === 'dock' && onClose && (
          <button
            type="button"
            onClick={onClose}
            title="Close chat"
            className="rounded-md p-2 text-gray-300 hover:bg-dark-800 hover:text-white"
          >
            <X size={18} aria-hidden="true" />
            <span className="sr-only">Close chat</span>
          </button>
        )}
      </header>

      <div className="border-b border-gray-200 bg-gray-50 px-3 py-2">
        <label htmlFor="opencode-model" className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-gray-500">
          Model
        </label>
        <select
          id="opencode-model"
          value={selectedValue}
          onChange={event => void changeModel(event.target.value)}
          disabled={streaming || loading || models.length === 0}
          className="w-full rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-sm disabled:opacity-60"
        >
          {!selectedValue && <option value="">{loading ? 'Loading models…' : 'No model available'}</option>}
          {grouped.map(([provider, items]) => (
            <optgroup key={provider} label={provider}>
              {items.map(item => (
                <option key={`${item.providerID}/${item.id}`} value={`${item.providerID}/${item.id}`}>
                  {item.name}{item.free ? ' (free)' : ''}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {!loading && models.length === 0 && (
          <p className="mt-1 text-[11px] text-red-600">
            No tool-capable model found. Check the Ollama / OpenCode provider configuration.
          </p>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto overscroll-contain bg-gray-50 px-3 py-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              Ask about any project, or tell the agent what to change. Enter sends, Shift+Enter adds a line.
            </p>
            <div className="flex flex-wrap gap-2">
              {starterPrompts.map(prompt => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void send(prompt)}
                  disabled={disabled}
                  className="rounded-full border border-gray-300 bg-white px-3 py-1 text-xs text-gray-700 hover:border-primary-500 hover:text-primary-700 disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(message => (
          <div
            key={message.id}
            className={clsx('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
          >
            <div
              className={clsx(
                'max-w-[88%] rounded-2xl px-3 py-2 text-sm shadow-sm',
                message.role === 'user'
                  ? 'rounded-br-sm bg-primary-600 text-white'
                  : message.error
                    ? 'rounded-bl-sm border border-red-200 bg-red-50 text-red-700'
                    : 'rounded-bl-sm border border-gray-200 bg-white text-gray-800',
              )}
            >
              {message.text
                ? <MessageBody text={message.text} />
                : message.pending
                  ? <span className="inline-flex items-center gap-2 text-gray-500"><Loader2 size={14} className="animate-spin" /> Thinking…</span>
                  : null}
              {message.error && message.text && (
                <p className="mt-1 text-xs font-medium text-red-600">{message.error}</p>
              )}
              {message.notice && (
                <p className="mt-1 text-xs font-medium text-amber-600">{message.notice}</p>
              )}
            </div>
          </div>
        ))}

        {status && (
          <p className="flex items-center gap-2 pl-1 text-xs text-gray-500">
            <Loader2 size={12} className="animate-spin" /> {status}
          </p>
        )}
        {error && !messages.some(message => message.error) && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="mt-1 font-medium underline disabled:opacity-50"
            >
              Retry
            </button>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-gray-200 bg-white px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="flex items-end gap-2">
          <textarea
            ref={composerRef}
            value={input}
            onChange={event => setInput(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
            rows={2}
            placeholder={loading ? 'Connecting to OpenCode…' : 'Ask OpenCode… (Enter to send)'}
            disabled={loading}
            enterKeyHint="send"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            className="max-h-40 min-h-[42px] flex-1 resize-y rounded-xl border border-gray-300 px-3 py-2 text-base focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:bg-gray-100 sm:text-sm"
          />
          {streaming ? (
            <button
              type="button"
              onClick={() => void stop()}
              title="Stop"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-red-600 text-white hover:bg-red-700"
            >
              <Square size={16} aria-hidden="true" />
              <span className="sr-only">Stop</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void send()}
              disabled={disabled || !input.trim()}
              title="Send"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
            >
              <Send size={16} aria-hidden="true" />
              <span className="sr-only">Send</span>
            </button>
          )}
        </div>
        <p className="mt-1 text-[11px] text-gray-400">
          Runs on this PC in {model ? `${model.providerID}/${model.id}` : 'the selected model'}.
        </p>
      </div>
    </section>
  );
}
