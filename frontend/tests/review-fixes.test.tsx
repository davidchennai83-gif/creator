import { it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AuthForm from '../src/components/AuthForm';
import Sidebar from '../src/components/Sidebar';
import { useAuthStore } from '../src/stores/authStore';

it('username pattern is a valid regular expression in browsers\' unicode-sets (v) mode', () => {
  render(<MemoryRouter><AuthForm register /></MemoryRouter>);
  const pattern = screen.getByLabelText('Username').getAttribute('pattern')!;
  expect(() => new RegExp(`^(?:${pattern})$`, 'v')).not.toThrow();
  expect(new RegExp(`^(?:${pattern})$`, 'v').test('creator_01-a')).toBe(true);
  expect(new RegExp(`^(?:${pattern})$`, 'v').test('bad name!')).toBe(false);
});

it('sidebar avatar shows the signed-in user initial', () => {
  useAuthStore.getState().setSession({id: '1', email: 'david@example.com', username: 'david', display_name: null, role: 'EDITOR', is_active: true}, 't');
  render(<MemoryRouter><Sidebar /></MemoryRouter>);
  expect(screen.getByText('D')).toBeInTheDocument();
});
