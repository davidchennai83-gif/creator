// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import VideoCreator from '../src/pages/VideoCreator';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../src/services/apiClient', () => ({ default: api, errorMessage: () => 'Delete failed' }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function setup(fail = false) {
  let jobs = [{ id: 'law-video', kind: 'indian-law', date: '2026-09-17', status: 'complete',
    message: 'Saved law video', points: [], model: 'curated', duration: 120 }];
  api.get.mockImplementation(async (path: string) => ({ data: { data:
    path.endsWith('/capabilities') ? { model: 'test', installed: true } : jobs } }));
  api.post.mockImplementation(async () => {
    if (fail) throw new Error('locked');
    jobs = [];
    return { data: { data: { deleted: true } } };
  });
  render(<VideoCreator />);
}

it('Delete button removes the gallery card and selected video details', async () => {
  setup();
  fireEvent.click(screen.getByRole('button', { name: /INDIAN LAW — DAILY 5 ACTS/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'View' }));
  expect(screen.getByText('Saved law video')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/video-creator/jobs/law-video/delete'));
  await waitFor(() => expect(screen.queryByText('Saved law video')).toBeNull());
  expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
});

it('Deletion failure keeps the video visible and displays an error', async () => {
  setup(true);
  fireEvent.click(screen.getByRole('button', { name: /INDIAN LAW — DAILY 5 ACTS/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Delete failed');
  expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy();
});
