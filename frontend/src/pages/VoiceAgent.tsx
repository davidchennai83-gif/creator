import { useCallback, useEffect, useRef, useState } from 'react';
import { Mic, Volume2, RefreshCw, Play, Radio, Server, HardDrive, Film, ShoppingBag, Upload } from 'lucide-react';
import api, { Envelope, errorMessage } from '../services/apiClient';
import clsx from 'clsx';

interface VoiceFindings {
  time: string; backend: boolean; ollama: boolean; recorder: boolean;
  disk_e_gb: number | null; disk_c_gb: number | null;
  renders_total: number; renders_complete: number; narration_ok: boolean; silent_videos: string[];
  uploads_today: number; pending_orders: number;
}
interface VoiceEvent { at: string; kind: string; text: string; spoken?: boolean; engine?: string }
interface VoiceConfig { enabled: boolean; interval_minutes: number; voice: string; speak_heartbeat: boolean; speak_alerts: boolean }
interface VoiceStatus { config: VoiceConfig; findings: VoiceFindings | null; events: VoiceEvent[]; checked_at: string | null; voices: Record<string, string>; running: boolean }
interface NarrationVideo { id: string; kind: string; status: string; has_narration: boolean; narrated_files: number; files: string[] }

const KIND_LABEL: Record<string, string> = { history: 'Day of History', 'indian-law': 'Indian Law', 'make-money': 'Make Money', news: 'Tamil News', thirukkural: 'Thirukkural', english: 'Spoken English', gk: 'Amazing Facts', health: 'Health Tips', motivation: 'Life Lessons', kids: 'Kids Learning' };

function Chip({ ok, label, icon: Icon }: { ok: boolean; label: string; icon: typeof Server }) {
  return (
    <div className={clsx('flex items-center gap-2 rounded-lg border px-3 py-2 text-sm',
      ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700')}>
      <Icon size={16} /><span className="font-medium">{label}</span>
      <span className="ml-auto text-xs">{ok ? 'online' : 'down'}</span>
    </div>
  );
}

export default function VoiceAgent() {
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [narration, setNarration] = useState<NarrationVideo[]>([]);
  const [cfg, setCfg] = useState<VoiceConfig | null>(null);
  const [say, setSay] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const timer = useRef<number | null>(null);

  const load = useCallback(() => {
    api.get<Envelope<VoiceStatus>>('/voice/status').then(r => { setStatus(r.data.data); setCfg(r.data.data.config); }).catch(e => setError(errorMessage(e)));
    api.get<Envelope<{ videos: NarrationVideo[] }>>('/voice/narration').then(r => setNarration(r.data.data.videos)).catch(() => {});
  }, []);

  useEffect(() => { load(); timer.current = window.setInterval(load, 30000); return () => { if (timer.current) window.clearInterval(timer.current); }; }, [load]);

  const act = async (name: string, fn: () => Promise<void>) => {
    setBusy(name); setError(''); setOk('');
    try { await fn(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(''); }
  };

  const saveConfig = () => act('save', async () => {
    if (!cfg) return;
    await api.post('/voice/config', cfg);
    setOk('Settings saved.');
    load();
  });

  const checkNow = () => act('check', async () => {
    await api.post('/voice/check');
    setOk('Check complete — announcement spoken on the machine.');
    load();
  });

  const speakNow = () => act('say', async () => {
    if (!say.trim()) return;
    await api.post('/voice/say', { text: say.trim(), voice: cfg?.voice, play: true });
    setOk('Spoken on the machine speakers.');
    setSay('');
    load();
  });

  const playLast = () => act('play', async () => {
    const r = await api.get('/voice/audio', { responseType: 'blob' });
    const url = URL.createObjectURL(r.data as Blob);
    await new Audio(url).play();
  });

  const f = status?.findings;

  return (
    <div className="p-4 md:p-6 space-y-4 max-w-5xl">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-bold flex items-center gap-2"><Radio size={22} className="text-primary-600" /> Voice Agent</h1>
        <span className={clsx('text-xs font-bold rounded-full px-2 py-1', status?.running ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600')}>
          {status?.running ? '● 24×7 running' : '○ stopped'}
        </span>
        <button onClick={load} className="ml-auto flex items-center gap-2 text-sm border rounded-lg px-3 py-2 hover:bg-slate-50">
          <RefreshCw size={16} className={busy === 'load' ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>
      <p className="text-sm text-slate-600">
        Village-style Tamil surveillance voice — watches Ollama, the recorder, disk space, today's renders (with narration), uploads and store orders, then speaks through the PC speakers.
        Last check: {status?.checked_at || '—'}
      </p>

      {error && <p role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</p>}
      {ok && <p role="status" className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm p-3 rounded">{ok}</p>}

      <div className="grid sm:grid-cols-3 gap-2">
        <Chip ok={!!f?.backend} label="Backend" icon={Server} />
        <Chip ok={!!f?.ollama} label="Ollama (LLM)" icon={Server} />
        <Chip ok={!!f?.recorder} label="Recorder browser" icon={Server} />
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 text-sm">
        <div className="bg-white rounded-xl border border-slate-200 p-3"><div className="flex items-center gap-2 text-slate-500 text-xs"><Film size={14} /> Today's renders</div><p className="text-lg font-bold mt-1">{f?.renders_complete ?? 0}/{f?.renders_total ?? 0}</p><p className={clsx('text-xs', f?.narration_ok === false ? 'text-red-600' : 'text-emerald-600')}>{f?.narration_ok === false ? '⚠ narration missing' : '✓ narration present'}</p></div>
        <div className="bg-white rounded-xl border border-slate-200 p-3"><div className="flex items-center gap-2 text-slate-500 text-xs"><Upload size={14} /> YouTube uploads logged</div><p className="text-lg font-bold mt-1">{f?.uploads_today ?? 0}</p><p className="text-xs text-slate-400">alerts when it grows</p></div>
        <div className="bg-white rounded-xl border border-slate-200 p-3"><div className="flex items-center gap-2 text-slate-500 text-xs"><ShoppingBag size={14} /> Pending orders</div><p className="text-lg font-bold mt-1">{f?.pending_orders ?? 0}</p></div>
        <div className="bg-white rounded-xl border border-slate-200 p-3"><div className="flex items-center gap-2 text-slate-500 text-xs"><HardDrive size={14} /> Disk free (E / C)</div><p className="text-lg font-bold mt-1">{f?.disk_e_gb ?? '—'} / {f?.disk_c_gb ?? '—'} GB</p>{f?.disk_e_gb != null && f.disk_e_gb < 15 && <p className="text-xs text-red-600">⚠ low space</p>}</div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <h2 className="font-bold text-sm flex items-center gap-2"><Mic size={16} /> Controls</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm"><span className="block text-xs font-semibold text-slate-600 mb-1">Voice</span>
            <select value={cfg?.voice || ''} onChange={e => setCfg(c => c && { ...c, voice: e.target.value })} className="border rounded-lg p-2 text-sm">
              {Object.entries(status?.voices || {}).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select></label>
          <label className="text-sm"><span className="block text-xs font-semibold text-slate-600 mb-1">Heartbeat every (min)</span>
            <input type="number" min={1} max={720} value={cfg?.interval_minutes ?? 15} onChange={e => setCfg(c => c && { ...c, interval_minutes: Number(e.target.value) })} className="border rounded-lg p-2 text-sm w-28" /></label>
          <label className="flex items-center gap-2 text-sm mt-5"><input type="checkbox" checked={cfg?.enabled ?? true} onChange={e => setCfg(c => c && { ...c, enabled: e.target.checked })} /> Enabled</label>
          <label className="flex items-center gap-2 text-sm mt-5"><input type="checkbox" checked={cfg?.speak_alerts ?? true} onChange={e => setCfg(c => c && { ...c, speak_alerts: e.target.checked })} /> Speak alerts</label>
          <label className="flex items-center gap-2 text-sm mt-5"><input type="checkbox" checked={cfg?.speak_heartbeat ?? true} onChange={e => setCfg(c => c && { ...c, speak_heartbeat: e.target.checked })} /> Speak heartbeat</label>
          <button onClick={saveConfig} disabled={busy === 'save'} className="bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">{busy === 'save' ? 'Saving…' : 'Save'}</button>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <button onClick={checkNow} disabled={busy === 'check'} className="flex items-center gap-2 border rounded-lg px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={16} /> Check now</button>
          <button onClick={playLast} disabled={busy === 'play'} className="flex items-center gap-2 border rounded-lg px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"><Play size={16} /> Play last announcement</button>
        </div>
        <div className="flex gap-2">
          <input value={say} onChange={e => setSay(e.target.value)} placeholder="Type something for the agent to say…" className="flex-1 border rounded-lg p-2.5 text-sm"
            onKeyDown={e => { if (e.key === 'Enter') speakNow(); }} />
          <button onClick={speakNow} disabled={busy === 'say' || !say.trim()} className="flex items-center gap-2 bg-slate-900 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"><Volume2 size={16} /> Speak</button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h2 className="font-bold text-sm mb-2">Auto-narration check — today's videos</h2>
        {narration.length === 0 ? <p className="text-sm text-slate-500">No renders yet today.</p> : (
          <ul className="divide-y">
            {narration.map(v => (
              <li key={v.id} className="flex items-center gap-3 py-2 text-sm">
                <span className="font-medium w-40">{KIND_LABEL[v.kind] || v.kind}</span>
                <span className="text-xs text-slate-500">{v.status}</span>
                <span className={clsx('ml-auto text-xs font-semibold rounded-full px-2 py-0.5',
                  v.status !== 'complete' ? 'bg-slate-100 text-slate-500'
                    : v.has_narration ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700')}>
                  {v.status !== 'complete' ? 'rendering' : v.has_narration ? `🔊 narrated (${v.narrated_files})` : '🔇 silent'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h2 className="font-bold text-sm mb-2">Announcement log</h2>
        {(status?.events || []).length === 0 ? <p className="text-sm text-slate-500">No announcements yet.</p> : (
          <ul className="divide-y max-h-80 overflow-y-auto">
            {[...(status?.events || [])].reverse().map((e, i) => (
              <li key={i} className="py-2 text-sm flex gap-3">
                <span className="text-xs text-slate-400 shrink-0 w-36">{e.at?.replace('T', ' ')}</span>
                <span className={clsx('text-xs font-bold shrink-0', e.kind === 'alert' ? 'text-red-600' : 'text-primary-600')}>{e.kind}</span>
                <span className="text-slate-700">{e.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
