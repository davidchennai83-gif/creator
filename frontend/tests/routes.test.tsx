import { it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../src/services/apiClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services/apiClient')>()),
  bootstrapSession: vi.fn(),
}));

import App from '../src/App';
import { useAuthStore } from '../src/stores/authStore';

const removed = ['/content/studio', '/content/library', '/calendar', '/analytics', '/ai', '/affiliate', '/products', '/orders', '/revenue', '/notifications'];
const user = {id: 'u1', email: 'creator@example.com', username: 'creator', display_name: null, role: 'EDITOR', is_active: true};

beforeEach(() => { useAuthStore.getState().setSession(user, 'token'); });

it.each(removed)('removed page %s shows the not-found page', (path) => {
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  expect(screen.getByRole('heading', {name: 'Page not found'})).toBeVisible();
});

it('sidebar lists only the pages that still exist', () => {
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  const nav = within(screen.getByRole('navigation', {hidden: true}));
  const labels = nav.getAllByRole('link', {hidden: true}).map(link => link.textContent);
  expect(labels).toEqual(['Dashboard', 'Video Creator', 'Task Scheduler', 'Social Media', 'Activity Logs', 'Settings']);
});

it('dashboard no longer links to removed content pages', () => {
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  expect(screen.getByRole('heading', {name: 'Creator dashboard'})).toBeVisible();
  expect(document.querySelector('a[href^="/content"]')).toBeNull();
});
