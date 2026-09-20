import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Film,
  Clock,
  Share2,
  FileText,
  Settings,
} from 'lucide-react';
import clsx from 'clsx';
import { useAuthStore, useUIStore } from '../stores';

const menuItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/video-creator', label: 'Video Creator', icon: Film },
  { path: '/scheduler', label: 'Task Scheduler', icon: Clock },
  { path: '/social', label: 'Social Media', icon: Share2 },
  { path: '/activity', label: 'Activity Logs', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];

const Sidebar: React.FC = () => {
  const user = useAuthStore(s=>s.user);
  const {sidebarOpen, closeSidebar} = useUIStore();
  return (
    <aside aria-label="Main navigation" className={clsx('w-64 shrink-0 bg-dark-900 text-white flex-col md:flex', sidebarOpen ? 'flex absolute z-30 h-full' : 'hidden')}>
      <div className="p-4 border-b border-dark-700">
        <h2 className="text-xl font-bold">Creator OS</h2>
        <button className="md:hidden mt-2" onClick={closeSidebar}>Close menu</button>
      </div>
      <nav className="flex-1 overflow-y-auto py-4">
        {menuItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={closeSidebar}
            end={item.path === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-3 text-sm transition-colors',
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-dark-800'
              )
            }
          >
            <item.icon size={20} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-dark-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-600 rounded-full flex items-center justify-center text-sm font-bold">
            {(user?.username?.[0] ?? '?').toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-medium">{user?.username}</p>
            <p className="text-xs text-gray-400">{user?.role}</p>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
