import { useEffect, useState } from 'react';
import { Sparkles, RefreshCw, HardDriveDownload, CheckCircle2, AlertTriangle, Bot } from 'lucide-react';
import api, { Envelope, errorMessage } from '../services/apiClient';
import clsx from 'clsx';

interface OpsConfig { ai_upgrade_enabled: boolean; backup_enabled: boolean; daily_report_enabled: boolean }
interface OpsStatus {
  day: string;
  config: OpsConfig;
  last_daily: string | null;
  last_ai: string | null;
  report: {
    day: string; at: string; ok: boolean;
    health?: Record<string, any>;
    store?: Record<string, any>;
    backups?: string[];
  } | null;
  ai_log: string;
  roadmap: string;
  cli_available: boolean;
  cli: string;
  project: string;
}

const inr = (n: number) => '₹' + (n || 0).toLocaleString('en-IN');

export default function Ops() {
  const [s, setS] = useState<OpsStatus | null>(null);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [busy, setBusy] = useState('');

  const load = () => api.get<Envelope<OpsStatus>>('/ops/status')
    .then(r => setS(r.data.data))
    .catch(e => setError(errorMessage(e)));
  useEffect(() => { void load(); const t = window.setInterval(() => void load(), 25000); return () => window.clearInterval(t); }, []);

  const notify = (m: string) => { setOk(m); setTimeout(() => setOk(''), 5000); };

  async function runNow() {
    setBusy('run'); setError('');
    try { await api.post('/ops/run', null, { params: { force: true } }); notify('Daily maintenance ran — backup + report + prune.'); await load(); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(''); }
  }
  async function upgradeNow() {
    setBusy('up'); setError('');
    try { const r = await api.post<Envelope<any>>('/ops/upgrade'); const d = r.data.data; notify(d.started ? `Self-upgrade started (pid ${d.pid}) — it works quietly in the background.` : `Not started: ${d.reason}`); await load(); }
    catch (e) { setError(errorMessage(e)); } finally { setBusy(''); }
  }
  async function toggle(key: keyof OpsConfig) {
    if (!s) return;
    const next = { ...s.config, [key]: !s.config[key] };
    setS({ ...s, config: next });
    try { await api.post('/ops/config', next); } catch (e) { setError(errorMessage(e)); }
  }

  const health = s?.report?.health || {};
  const money = s?.report?.store || {};

  const roadmapLines = (s?.roadmap || '').split('\n');

  return (
    <section className="space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold flex items-center gap-2"><Sparkles className="text-violet-500" /> Autonomous Ops</h1>
          <p className="text-sm text-slate-500">The platform maintains and upgrades itself every day — no babysitting.</p>
        </div>
        <button onClick={() => void load()} className="border rounded-lg px-3 py-2 text-sm flex items-center gap-1"><RefreshCw size={14} />Refresh</button>
      </div>

      {error && <p role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</p>}
      {ok && <p role="status" className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm p-3 rounded">{ok}</p>}

      {!s ? <p className="text-sm text-slate-400 py-8 text-center">Loading…</p> : (
        <>
          {/* status strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs font-semibold text-violet-600 flex items-center gap-1"><Bot size={14} />Self-upgrade</p>
              <p className={clsx('text-lg font-extrabold', s.cli_available ? 'text-emerald-600' : 'text-red-500')}>{s.cli_available ? 'Ready' : 'CLI missing'}</p>
              <p className="text-[11px] text-slate-400">last: {s.last_ai || 'never'}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs font-semibold text-slate-600 flex items-center gap-1"><HardDriveDownload size={14} />Maintenance</p>
              <p className="text-lg font-extrabold">{s.last_daily || 'never'}</p>
              <p className="text-[11px] text-slate-400">backup · report · prune</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs font-semibold text-emerald-600">Health today</p>
              <p className={clsx('text-lg font-extrabold flex items-center gap-1', s.report?.ok ? 'text-emerald-600' : 'text-amber-600')}>
                {s.report ? (s.report.ok ? <><CheckCircle2 size={16} />OK</> : <><AlertTriangle size={16} />Check</>) : '—'}
              </p>
              <p className="text-[11px] text-slate-400">{health.renders_complete ?? 0}/{health.renders_total ?? 0} videos · narration {health.narration_ok ? 'ok' : 'no'}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <p className="text-xs font-semibold text-orange-600">Earnings snapshot</p>
              <p className="text-lg font-extrabold">{inr(money.revenue_confirmed)}</p>
              <p className="text-[11px] text-slate-400">{money.orders_total ?? 0} orders · {money.affiliate_clicks ?? 0} clicks</p>
            </div>
          </div>

          {/* controls */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h2 className="font-bold text-sm">Controls</h2>
            <div className="flex flex-wrap gap-2">
              <button disabled={!s.cli_available || busy === 'up'} onClick={() => void upgradeNow()}
                className="bg-violet-600 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50 flex items-center gap-1">
                <Sparkles size={15} />{busy === 'up' ? 'Starting…' : 'Upgrade now'}</button>
              <button disabled={busy === 'run'} onClick={() => void runNow()}
                className="bg-slate-900 text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50 flex items-center gap-1">
                <HardDriveDownload size={15} />{busy === 'run' ? 'Running…' : 'Run maintenance now'}</button>
            </div>
            <div className="flex flex-wrap gap-4 text-sm pt-1">
              {([
                ['ai_upgrade_enabled', 'Daily self-upgrade'],
                ['backup_enabled', 'Daily backups'],
                ['daily_report_enabled', 'Daily report'],
              ] as [keyof OpsConfig, string][]).map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={!!s.config[key]} onChange={() => void toggle(key)} className="accent-violet-600 w-4 h-4" />
                  {label}
                </label>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">Daily self-upgrade runs once a day (IST) and ships one safe improvement from the roadmap. It backs up first, tests, and only backend changes wait for the watchdog to restart when no render is running.</p>
          </div>

          {/* today's report */}
          {s.report && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h2 className="font-bold text-sm mb-2">Today's report — {s.report.day} <span className="text-slate-400 font-normal">({new Date(s.report.at).toLocaleTimeString('en-IN')})</span></h2>
              <div className="grid sm:grid-cols-2 gap-2 text-sm text-slate-600">
                <p>🗄️ Backups: <b>{(s.report.backups || []).length}</b> file(s)</p>
                <p>📼 Videos: <b>{health.renders_complete ?? 0}/{health.renders_total ?? 0}</b> · narration {health.narration_ok ? '✅' : '⚠️'}</p>
                <p>🧠 Ollama: {health.ollama ? '✅' : '❌'} · Recorder: {health.recorder ? '✅' : '❌'}</p>
                <p>💾 E: <b>{health.disk_e_gb ?? '—'} GB</b> · C: <b>{health.disk_c_gb ?? '—'} GB</b></p>
                <p>🎬 Uploads logged: <b>{health.uploads_today ?? 0}</b></p>
                <p>🛒 Pending orders: <b>{health.pending_orders ?? 0}</b></p>
              </div>
              {(s.report.backups || []).length > 0 && <p className="text-[11px] text-slate-400 mt-2 truncate">{(s.report.backups || []).join(', ')}</p>}
            </div>
          )}

          {/* AI log */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h2 className="font-bold text-sm mb-2">Self-upgrade log (today)</h2>
            {s.ai_log ? <pre className="text-[11px] leading-relaxed bg-slate-900 text-slate-100 rounded-lg p-3 max-h-72 overflow-auto whitespace-pre-wrap">{s.ai_log}</pre>
              : <p className="text-xs text-slate-400">No autonomous upgrade has run today yet. It runs at the next date change (or tap “Upgrade now”).</p>}
          </div>

          {/* roadmap */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <h2 className="font-bold text-sm mb-2">Roadmap (UPGRADES.md)</h2>
            <div className="max-h-96 overflow-auto space-y-0.5">
              {roadmapLines.map((line, i) => {
                const m = line.match(/^- \[( |x)\] (.*)$/);
                if (m) {
                  const done = m[1] === 'x';
                  return <p key={i} className={clsx('text-sm flex gap-2', done ? 'text-slate-400 line-through' : 'text-slate-700')}>
                    <span>{done ? '✅' : '⬜'}</span>{m[2]}</p>;
                }
                if (line.startsWith('#')) return <p key={i} className="text-sm font-bold mt-2">{line.replace(/^#+\s*/, '')}</p>;
                return line.trim() ? <p key={i} className="text-xs text-slate-500">{line}</p> : null;
              })}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
