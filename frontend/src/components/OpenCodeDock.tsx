import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Bot, X } from 'lucide-react';
import clsx from 'clsx';
import OpenCodeChat from './OpenCodeChat';
import { useAuthStore } from '../stores';

/**
 * Floating OpenCode launcher available on every signed-in page.
 * The panel stays mounted while closed so a running reply keeps streaming.
 */
export default function OpenCodeDock() {
  const [open, setOpen] = useState(false);
  // Do not contact the agent (or start it) until the user opens the panel once.
  const [mounted, setMounted] = useState(false);
  // Mobile keyboards change the visual viewport without changing 100dvh on iOS.
  const [keyboardBox, setKeyboardBox] = useState<{ height: number; top: number } | null>(null);
  const [narrow, setNarrow] = useState(false);
  const location = useLocation();
  const role = useAuthStore(state => state.user?.role);

  // Track the phone breakpoint so rotating to landscape drops the inline height.
  useEffect(() => {
    const media = window.matchMedia('(max-width: 639px)');
    const update = () => setNarrow(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!open || !narrow || !window.visualViewport) return;
    const viewport = window.visualViewport;
    const update = () => setKeyboardBox({ height: viewport.height, top: viewport.offsetTop });
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
      setKeyboardBox(null);
    };
  }, [open, narrow]);

  // The full-screen mobile panel should not scroll the page underneath it.
  useEffect(() => {
    if (!open || !narrow) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open, narrow]);

  // The dedicated /opencode page renders the same chat full-size.
  if (location.pathname === '/opencode') return null;
  // Only roles allowed to run automation may reach the agent.
  if (!role || !['SUPER_ADMIN', 'ADMIN', 'EDITOR'].includes(role)) return null;

  return (
    <>
      <div
        id="opencode-dock"
        style={open && narrow && keyboardBox ? { height: keyboardBox.height, top: keyboardBox.top, bottom: 'auto' } : undefined}
        className={clsx(
          'fixed z-40 h-[100dvh] w-full',
          'inset-0 sm:inset-auto sm:bottom-24 sm:right-5 sm:h-[min(660px,calc(100dvh-8rem))] sm:w-[min(430px,calc(100vw-1.5rem))]',
          open ? 'block' : 'hidden',
        )}
      >
        {mounted && <OpenCodeChat variant="dock" onClose={() => setOpen(false)} />}
      </div>
      <button
        type="button"
        onClick={() => {
          setMounted(true);
          setOpen(value => !value);
        }}
        className={clsx(
          'fixed bottom-5 right-3 z-40 items-center gap-2 rounded-full bg-dark-900 px-4 py-3 text-sm font-medium text-white shadow-xl transition-colors hover:bg-dark-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 sm:right-5',
          // The full-screen panel already has a close button.
          open ? 'hidden sm:flex' : 'flex',
        )}
        aria-expanded={open}
        aria-controls="opencode-dock"
      >
        {open ? <X size={18} aria-hidden="true" /> : <Bot size={18} aria-hidden="true" />}
        {open ? 'Close' : 'OpenCode'}
      </button>
    </>
  );
}
