import { useEffect, useState } from 'react';
import api, { Envelope, errorMessage } from '../services/apiClient';
import ShareMenu from '../components/ShareMenu';

interface Point { year: string; title?: string; sections?: string; text: string; lines: string[]; links: {title: string; link: string}[] }
interface Job { id: string; kind?: 'history' | 'indian-law'; date: string; status: string; message: string; points: Point[]; duration?: number; model: string; media_sources?: {scene: number; provider: string; source_url?: string; photographer?: string}[] }
interface Capabilities { model: string; installed: boolean; mode: string; internet_required: string }

export default function VideoCreator() {
  const [cap, setCap] = useState<Capabilities>();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'history' | 'indian-law'>('history');
  const isLaw = kind === 'indian-law';
  const [preview, setPreview] = useState<string | null>(null);
  const [day, setDay] = useState(new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kolkata', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date()));
  const [voice, setVoice] = useState('ta-IN-PallaviNeural');
  const visibleJobs = jobs.filter(j => (j.kind || 'history') === kind);
  const job = visibleJobs.find(j => j.id === selected);
  const active = jobs.some(j => ['writing','rendering'].includes(j.status));
  const load = async () => { const r = await api.get<Envelope<Job[]>>('/video-creator/jobs'); setJobs(r.data.data); };
  useEffect(() => {
    void api.get<Envelope<Capabilities>>('/video-creator/capabilities').then(r=>setCap(r.data.data)).catch(e=>setError(errorMessage(e)));
    void load().catch(e=>setError(errorMessage(e)));
  }, []);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(()=>{ void load().catch(e=>setError(errorMessage(e))); }, 5000);
    return ()=>window.clearInterval(timer);
  }, [active]);
  useEffect(()=>()=>{ if(preview) URL.revokeObjectURL(preview); },[preview]);
  async function action(path: string, data = {}) {
    setBusy(true); setError(''); setSelected(undefined); setPreview(null);
    try {
      const r = await api.post<Envelope<Job>>(path, data);
      if ((r.data.data.kind || 'history') !== kind) throw new Error('Wrong video type returned. Restart the backend.');
      setSelected(r.data.data.id); await load();
    }
    catch(e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function deleteJob(jid: string) {
    setBusy(true); setError('');
    try {
      await api.post(`/video-creator/jobs/${jid}/delete`);
      setJobs(current=>current.filter(j=>j.id !== jid));
      if (selected === jid) { setSelected(undefined); setPreview(null); }
      await load();
    }
    catch(e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function download(j: Job, saveFile = false) {
    setBusy(true); setError('');
    try { const r = await api.get(`/video-creator/jobs/${j.id}/download`, {responseType:'blob', timeout:120000}); const url = URL.createObjectURL(r.data); if (saveFile) { const link = document.createElement('a'); link.href = url; link.download = `${j.kind==='indian-law' ? 'indian-law' : 'day-of-history'}-${j.date}-${j.id.slice(0,8)}.mp4`; document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(()=>URL.revokeObjectURL(url), 60000); } else { setSelected(j.id); setPreview(url); } }
    catch(e) {setError(errorMessage(e));} finally {setBusy(false);}
  }
  return (
    <section className="space-y-6 max-w-5xl">
      <h1 className="text-3xl font-bold">Video Creator</h1>
      <p>Ollama Tamil scripts · Neural Tamil narration · Background music · MP4 export</p>
      <div className="grid sm:grid-cols-2 gap-4">
        <button disabled={busy} onClick={()=>{setKind('history');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-slate-900 text-white p-8 w-full border border-teal-500">
          <span className="text-teal-300 text-sm">TODAY, ACROSS WORLD HISTORY</span>
          <h2 className="text-2xl font-bold mt-2">DAY OF HISTORY</h2>
          <p lang="ta" className="mt-3">இன்றைய தேதியில் நடந்த 10 முக்கிய நிகழ்வுகள் — தமிழில் காணொளி.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('indian-law');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-indigo-950 text-white p-8 w-full border border-amber-500">
          <span className="text-amber-300 text-sm">DAILY LEGAL AWARENESS · TAMIL</span>
          <h2 className="text-2xl font-bold mt-2">INDIAN LAW — DAILY 5 ACTS</h2>
          <p lang="ta" className="mt-3">தினமும் 5 இந்தியச் சட்டங்கள் — ஒவ்வொரு சட்டத்திற்கும் 4 வரி விளக்கம்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
      </div>
      {error && <p role="alert" className="bg-red-50 p-4 text-red-700">{error}</p>}
      {open && <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-bold text-xl">{isLaw ? "Create today's Indian Law video" : "Create today's history video"}</h2>
        <p>{isLaw ? '5 Acts, four Tamil sentences each.' : '10 events, two Tamil sentences each.'} Duration follows natural narration.</p>
        <p className="text-sm">Narrated text scenes with Tamil voice and BGM. Internet is required for neural speech.</p>
        {isLaw && <p className="text-sm">Date-based daily selection from a 15-Act introductory catalog; repeats every 3 days. General central-law explanations with section references and India Code lookup links. These are curated topics, not a live amendment feed. Start each day's video with the button below.</p>}
        <p>Script: <b>{isLaw ? 'Curated Tamil legal explanations' : cap?.model || 'Checking…'}</b> {!isLaw && cap && !cap.installed && '— not installed / Ollama unavailable'}</p>
        <label className="block">{isLaw ? 'Daily edition date' : 'Historical month/day'} <input type="date" value={day} onChange={e=>setDay(e.target.value)} className="border p-2 ml-3" /></label>
        <label className="block">Tamil voice <select value={voice} onChange={e=>setVoice(e.target.value)} className="border p-2 ml-3"><option value="ta-IN-PallaviNeural">Pallavi — female</option><option value="ta-IN-ValluvarNeural">Valluvar — male</option></select></label>
        <button disabled={busy || active || !day || (!isLaw && !cap?.installed)} onClick={()=>void action('/video-creator/jobs', {day,voice,kind})} className="bg-teal-700 text-white rounded px-5 py-3 disabled:opacity-50">{isLaw ? 'Generate 5 Acts in Tamil' : 'Generate 10 Tamil points'}</button>
        <p className="text-sm">Local CPU generation can take several minutes. You can navigate away and return.</p>
      </div>}
      {jobs.length > 0 && <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-bold mb-3">Your videos</h2>
        <div className="flex flex-col sm:flex-row gap-2 overflow-x-auto">
          {visibleJobs.map(j=><div key={j.id} className="shrink-0 min-w-[200px] bg-slate-900 text-white rounded-lg p-4 flex flex-col">
            <div className="font-bold truncate">{j.kind==='indian-law' ? 'Indian Law' : 'History'}</div>
            <div className="text-xs text-amber-400 mt-1">{j.date}</div>
            <div className="text-xs mt-1">{j.status}</div>
            <button disabled={busy} onClick={()=>{setSelected(j.id);setPreview(null);}} className="text-teal-300 mt-2">View</button>
            {j.status === 'complete' && <div className="space-y-2 mt-2">
              <button disabled={busy} onClick={()=>void download(j, true)} className="bg-teal-700 text-white p-2 rounded">Download MP4</button>
              <ShareMenu />
            </div>}
            <button disabled={busy || active} onClick={()=>void deleteJob(j.id)} className="text-red-400 text-xs mt-2 disabled:opacity-50">Delete</button>
          </div>)}
        </div>
        {visibleJobs.length === 0 && <p className="text-sm text-slate-500">No videos in this mode yet.</p>}
      </div>}
      {job && <article className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-bold text-xl">{job.kind==='indian-law' ? 'Indian Law' : 'History'} · {job.date} — {job.status}</h2>
        <p role="status">{job.message}</p>
        {job.points.map((p,i)=><div key={i} className="border-b pb-4"><h3 className="font-bold">{i+1}. {p.title || p.year}</h3>{p.lines.map((l,n)=><p lang="ta" key={n} className="my-2">{l}</p>)}<details><summary>{job.kind==='indian-law' ? 'Reference facts and Act lookup' : 'Check original source'}</summary><p>{p.text}</p>{p.sections && <p>Section references: {p.sections}</p>}{p.links.map(l=><a key={l.link} href={l.link} target="_blank" rel="noreferrer" className="text-blue-700 block underline">{l.title}</a>)}</details></div>)}
        {job.status==='review' && <div>
          <p>Review the Tamil summaries against the linked sources before rendering.</p>
          <button disabled={busy || active} onClick={()=>void action(`/video-creator/jobs/${job.id}/render`)} className="bg-teal-700 text-white p-3 rounded disabled:opacity-50">Generate video with voice + BGM</button>
        </div>}
        {job.status==='complete' && <div className="space-y-3">
          <p>Duration: {job.duration} seconds</p>
          <button disabled={busy} onClick={()=>void download(job)} className="bg-teal-700 text-white p-3 rounded">Load video</button>
          <button disabled={busy} onClick={()=>void download(job, true)} className="bg-teal-700 text-white p-3 rounded ml-2">Download MP4</button>
          <ShareMenu />
          {preview && <video controls src={preview} className="w-full rounded mt-2"/>}
          {job.media_sources && <details><summary>Photo credits / Pexels</summary>
            {job.media_sources.map(source=><p key={source.scene}>Scene {source.scene}: {source.provider === 'pexels' && source.source_url?.startsWith('https://www.pexels.com/') ? <a href={source.source_url} target="_blank" rel="noreferrer" className="underline">{source.photographer} / Pexels</a> : 'Local illustration'}</p>)}
          </details>}
        </div>}
        {job.status!=='complete' && job.status!=='review' && <p className="text-sm text-slate-500">Pending generation…</p>}
      </article>}
    </section>
  );
}
