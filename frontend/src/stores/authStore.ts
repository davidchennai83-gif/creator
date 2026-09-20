import { create } from 'zustand';
export interface User { id: string; email: string; username: string; display_name: string | null; role: string; is_active: boolean }
interface State { user: User | null; token: string | null; ready: boolean; setSession: (user: User, token: string) => void; clear: () => void }
// Access tokens stay in memory. Browser refresh token is an HttpOnly cookie.
export const useAuthStore = create<State>()((set) => ({
  user: null, token: null, ready: false,
  setSession: (user, token) => set({user, token, ready: true}),
  clear: () => set({user: null, token: null, ready: true}),
}));
