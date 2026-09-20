import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authService, errorMessage } from '../services/apiClient';
import { Input } from './common/Form';
import { Button } from './common/Button';

export default function AuthForm({register=false}: {register?: boolean}) {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const navigate = useNavigate();
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { if (register) await authService.register({email, password, username}); else await authService.login({email, password}); navigate('/'); }
    catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  }
  return <section className="card"><h2 className="text-2xl font-bold mb-6">{register ? 'Create account' : 'Welcome back'}</h2>
    <form onSubmit={submit} className="space-y-4">
      {register && <Input label="Username" required minLength={3} maxLength={100} pattern="[a-zA-Z0-9_\-]+" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} />}
      <Input label="Email" type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} />
      <Input label="Password" type="password" required minLength={register ? 12 : 1} maxLength={128} autoComplete={register ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} />
      {register && <p className="text-sm text-gray-500">Use at least 12 characters.</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <Button type="submit" loading={busy} className="w-full">{register ? 'Create account' : 'Sign in'}</Button>
    </form>
    <Link className="block mt-4 text-blue-700 underline" to={register ? '/login' : '/register'}>{register ? 'Already registered? Sign in' : 'Create a new account'}</Link>
  </section>;
}
