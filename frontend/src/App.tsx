import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import ActivityLogs from './pages/ActivityLogs';
import Settings from './pages/Settings';
import VideoCreator from './pages/VideoCreator';
import Social from './pages/Social';
import Scheduler from './pages/Scheduler';
import { PlannedPage, NotFoundPage } from './pages';
import { useAuthStore } from './stores/authStore';
import { bootstrapSession } from './services/apiClient';

export default function App() {
  const { user, ready } = useAuthStore();
  useEffect(() => { void bootstrapSession(); }, []);
  if (!ready) return <p className="p-8" role="status">Connecting to your workspace…</p>;
  return <Routes>
    <Route element={<AuthLayout />}>
      <Route path="login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="register" element={user ? <Navigate to="/" replace /> : <Register />} />
      <Route path="forgot-password" element={<PlannedPage title="Password recovery" />} />
    </Route>
    <Route element={user ? <MainLayout /> : <Navigate to="/login" replace />}>
      <Route index element={<Dashboard />} />
      <Route path="social" element={<Social />} />
      <Route path="scheduler" element={<Scheduler />} />
      <Route path="video-creator" element={<VideoCreator />} />
      <Route path="activity" element={<ActivityLogs />} />
      <Route path="settings" element={<Settings />} />
      {['publish', 'customers'].map(path =>
        <Route key={path} path={path} element={<PlannedPage title={path} />} />)}
      <Route path="*" element={<NotFoundPage />} />
    </Route>
  </Routes>;
}
