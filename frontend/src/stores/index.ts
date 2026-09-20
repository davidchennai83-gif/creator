import { create } from 'zustand';
export { useAuthStore } from './authStore';
export const useUIStore = create<{sidebarOpen: boolean; toggleSidebar: () => void; closeSidebar: () => void}>()((set) => ({
  sidebarOpen: false,
  toggleSidebar: () => set(s => ({sidebarOpen: !s.sidebarOpen})),
  closeSidebar: () => set({sidebarOpen: false}),
}));
