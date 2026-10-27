import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '../stores/authStore';

export interface RecorderAgent {
  sid: string;
  version: string | null;
  platform: string | null;
  hostname: string;
  connected_at: string;
}

export interface RecorderEvent {
  type: string;
  msg?: string;
  name?: string;
  record_type?: string;
  event_count?: number;
}

/** Socket.IO shares the API host: the backend serves both /api/v1 and /socket.io. */
function resolveHub(): string {
  const configured = import.meta.env.VITE_API_URL;
  if (configured && /^https?:\/\//i.test(configured)) return new URL(configured).origin;
  return window.location.origin;
}

let socket: Socket | null = null;
let unsubscribe: (() => void) | null = null;

export function recorderSocket(): Socket {
  if (!socket) {
    // The hub rejects unauthenticated sockets, so each handshake carries the
    // current access token; sign-in/refresh updates are pushed into socket.auth
    // so later reconnects keep working.
    socket = io(resolveHub(), {
      path: '/socket.io',
      auth: { token: useAuthStore.getState().token },
      transports: ['websocket', 'polling'],
      autoConnect: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });
    unsubscribe = useAuthStore.subscribe((state) => {
      if (socket) socket.auth = { token: state.token };
    });
  }
  return socket;
}

export function closeRecorderSocket(): void {
  unsubscribe?.();
  unsubscribe = null;
  socket?.disconnect();
  socket = null;
}
