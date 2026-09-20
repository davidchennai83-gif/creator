import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore, User } from '../stores/authStore';

export interface Envelope<T> { success: boolean; data: T; message: string; error: {id?: string} | null }
interface Session { access_token: string; user: User }
const baseURL = import.meta.env.VITE_API_URL || '/api/v1';
const sessionClient = axios.create({baseURL, withCredentials: true, timeout: 15000});
const apiClient = axios.create({baseURL, withCredentials: true, timeout: 15000});
let pendingRefresh: Promise<void> | null = null;

function acceptSession(data: Session) { useAuthStore.getState().setSession(data.user, data.access_token); }
export function refreshSession(): Promise<void> {
  if (!pendingRefresh) {
    pendingRefresh = sessionClient.post<Envelope<Session>>('/auth/refresh').then(r => acceptSession(r.data.data))
      .catch(error => { useAuthStore.getState().clear(); throw error; }).finally(() => { pendingRefresh = null; });
  }
  return pendingRefresh;
}
export async function bootstrapSession() { try { await refreshSession(); } catch { /* Login screen handles missing session. */ } }

apiClient.interceptors.request.use(config => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
apiClient.interceptors.response.use(r => r, async (error: AxiosError) => {
  const config = error.config as (InternalAxiosRequestConfig & {_retried?: boolean}) | undefined;
  if (error.response?.status === 401 && config && !config._retried) {
    config._retried = true;
    await refreshSession();
    return apiClient(config);
  }
  throw error;
});
export function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data;
    if (body?.message) return `${body.message}${body.error?.id ? ` (ID: ${body.error.id})` : ''}`;
    if (!error.response) return 'Cannot reach the server. Check that Hypercorn is running.';
  }
  return 'Something went wrong. Please try again.';
}
export const authService = {
  async login(data: {email: string; password: string}) { const r = await sessionClient.post<Envelope<Session>>('/auth/login', data); acceptSession(r.data.data); },
  async register(data: {email: string; password: string; username: string}) { const r = await sessionClient.post<Envelope<Session>>('/auth/register', data); acceptSession(r.data.data); },
  async logout() { await apiClient.post('/auth/logout'); useAuthStore.getState().clear(); },
};
export default apiClient;
