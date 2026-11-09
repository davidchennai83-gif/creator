import { refreshSession } from './apiClient';
import { useAuthStore } from '../stores/authStore';

const baseURL = import.meta.env.VITE_API_URL || '/api/v1';

export interface ModelRef { id: string; providerID: string; variant?: string }
export interface AgentModel extends ModelRef { name: string; free: boolean; status?: string; context?: number; tools?: boolean }
export interface ModelCatalogue { models: AgentModel[]; default: ModelRef | null; providers: string[] }
export interface AgentSession { id: string; title?: string; model?: ModelRef }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; text: string; created?: number; error?: string; notice?: string; pending?: boolean }

export type StreamEvent =
  | { type: 'accepted' | 'started' | 'step' | 'done' | 'interrupted'; sessionID?: string; agent?: string; outcome?: string }
  | { type: 'delta' | 'text'; sessionID?: string; text: string }
  | { type: 'text-start'; sessionID?: string; ordinal?: number }
  | { type: 'tool'; sessionID?: string; name: string }
  | { type: 'tool-done'; sessionID?: string }
  | { type: 'notice'; sessionID?: string; message: string }
  | { type: 'error'; sessionID?: string; message: string };

function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const response = await fetch(baseURL + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init.headers || {}) },
  });
  if (response.status === 401 && retry) {
    await refreshSession();
    return request<T>(path, init, false);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.message || body?.detail || `Request failed (${response.status})`);
  }
  return body?.data as T;
}

export const opencodeService = {
  models: () => request<ModelCatalogue>('/agent/models'),
  createSession: (model: ModelRef, title?: string) =>
    request<AgentSession>('/agent/sessions', { method: 'POST', body: JSON.stringify({ model, title }) }),
  messages: (sessionId: string) => request<ChatMessage[]>(`/agent/sessions/${sessionId}/messages`),
  setModel: (sessionId: string, model: ModelRef) =>
    request<null>(`/agent/sessions/${sessionId}/model`, { method: 'POST', body: JSON.stringify({ model }) }),
  interrupt: (sessionId: string) =>
    request<null>(`/agent/sessions/${sessionId}/interrupt`, { method: 'POST' }),
};

/** Read the SSE body of /agent/chat and yield one parsed frame at a time. */
export async function* streamReply(
  sessionId: string,
  text: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  let response = await fetch(`${baseURL}/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ sessionId, text }),
    signal,
  });
  if (response.status === 401) {
    await refreshSession();
    response = await fetch(`${baseURL}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ sessionId, text }),
      signal,
    });
  }
  if (!response.ok || !response.body) {
    const body = await response.text().catch(() => '');
    throw new Error(body.slice(0, 300) || `OpenCode request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary >= 0) {
        const chunk = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const payload = chunk
          .split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trim())
          .join('\n');
        if (payload) {
          try {
            yield JSON.parse(payload) as StreamEvent;
          } catch {
            /* Ignore keep-alive or malformed frames. */
          }
        }
        boundary = buffer.indexOf('\n\n');
      }
    }
  } finally {
    reader.releaseLock();
  }
}
