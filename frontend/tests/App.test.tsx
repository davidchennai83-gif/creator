import { it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Login from '../src/pages/Login';
import { authService } from '../src/services/apiClient';
import { useAuthStore } from '../src/stores/authStore';

beforeEach(()=>{vi.restoreAllMocks();useAuthStore.getState().clear();});
it('failed authentication stays on the form and shows an error',async()=>{
  vi.spyOn(authService,'login').mockRejectedValue(new Error('failure'));
  render(<MemoryRouter><Login /></MemoryRouter>);
  await act(async()=>{
    await userEvent.type(screen.getByLabelText('Email'),'creator@example.com');
    await userEvent.type(screen.getByLabelText('Password'),'wrong');
    await userEvent.click(screen.getByRole('button',{name:'Sign in'}));
  });
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(useAuthStore.getState().user).toBeNull();
});
it('successful authentication navigates to the dashboard',async()=>{
  const login=vi.spyOn(authService,'login').mockResolvedValue();
  render(<MemoryRouter initialEntries={['/login']}><Routes><Route path="/login" element={<Login />} /><Route path="/" element={<h1>Dashboard destination</h1>} /></Routes></MemoryRouter>);
  await act(async()=>{
    await userEvent.type(screen.getByLabelText('Email'),'creator@example.com');
    await userEvent.type(screen.getByLabelText('Password'),'example password');
    await userEvent.click(screen.getByRole('button',{name:'Sign in'}));
  });
  expect(await screen.findByText('Dashboard destination')).toBeVisible();
  expect(login).toHaveBeenCalledWith({email:'creator@example.com',password:'example password'});
});
