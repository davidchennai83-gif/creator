import { useEffect, useState } from 'react';
import api, { Envelope, errorMessage } from '../services/apiClient';
import ShareMenu from '../components/ShareMenu';
import { TAMIL_VOICES } from '../constants/voices';

type Kind = 'history' | 'indian-law' | 'make-money' | 'news' | 'thirukkural' | 'english' | 'gk' | 'health' | 'motivation' | 'kids' | 'meesho';
interface Point { year?: string; title?: string; title_display?: string; title_en?: string; title_ta?: string; sections?: string; text: string; lines: string[]; lines_display?: string[]; links?: {title: string; link: string}[]; product_id?: string; product_title?: string; product_title_ta?: string; category?: string; price?: number; mrp?: number; rating?: number; orders_count?: number; features?: string[]; cautions?: string[]; short_url?: string; demo?: boolean; image_url?: string }
interface Job { id: string; kind?: Kind; date: string; status: string; message: string; points: Point[]; duration?: number; model: string; media_sources?: {scene: number; provider: string; source_url?: string; photographer?: string; license?: string}[]; subtitles?: {start: number; end: number; text: string}[] }
interface Capabilities { model: string; installed: boolean; mode: string; internet_required: string }

interface KindConfig { label: string; file: string; createTitle: string; shape: string; script?: string; dateLabel: string; generate: string; details: string; note?: string }
const KINDS: Record<Kind, KindConfig> = {
  'history': { label: 'History', file: 'day-of-history', createTitle: "Create today's history video", shape: '10 events, two Tamil sentences each.',
    dateLabel: 'Historical month/day', generate: 'Generate 10 Tamil points', details: 'Check original source',
    note: 'Portrait 9:16 MP4. Each scene is a moving shot — every chapter photo slowly zooms, pans and breathes with drifting depth, then dissolves into the next scene; narration is timed scene-by-scene, Tamil subtitles sync to each spoken word, and a soft ambient bed sits underneath. When an AI video provider is configured, scenes become real AI-animated clips instead of the local motion fallback.' },
  'indian-law': { label: 'Indian Law', file: 'indian-law', createTitle: "Create today's Indian Law video", shape: '5 Acts, four Tamil sentences each.',
    script: 'Curated Tamil legal explanations', dateLabel: 'Daily edition date', generate: 'Generate 5 Acts in Tamil', details: 'Reference facts and Act lookup',
    note: "Date-based daily selection from a 15-Act introductory catalog; repeats every 3 days. Written in natural spoken Tamil (YouTube/Instagram style), not textbook Tamil, with reference sections and India Code lookup links. These are curated topics, not a live amendment feed." },
  'make-money': { label: 'Make Money', file: 'make-money', createTitle: "Create today's How to Make Money video", shape: '5 money ideas, four Tamil lines each.',
    script: 'Curated Tamil money ideas', dateLabel: 'Daily edition date', generate: 'Generate 5 money ideas in Tamil', details: 'Reference facts and official links',
    note: 'Date-based daily selection from a 30-idea catalog; repeats every 6 days. Practical general ideas in natural spoken Tamil (YouTube/Instagram style). Educational only: no income is guaranteed and this is not financial advice.' },
  'news': { label: 'Tamil News', file: 'tamil-news', createTitle: "Create today's Tamil news video", shape: '10 recent Tamil news stories with source images and credits.',
    script: 'Live Tamil RSS feeds (no model needed)', dateLabel: 'Daily bulletin date', generate: 'Generate 10 news stories', details: 'RSS sources and images',
    note: 'Ten stories from public Tamil publisher RSS feeds (BBC Tamil, Daily Thanthi, Hindu Tamil, Polimer News, Maalai Malar, Sathiyam TV). Each scene shows the publisher image, two short attributed sentences from the publisher summary, and an on-screen source credit; the description lists every source link. Set NEWS_AI_REWRITE=true to rewrite in our own words with the local model. Feed images belong to their publishers — review the source list before monetising.' },
  'thirukkural': { label: 'Thirukkural', file: 'thirukkural', createTitle: "Create today's Thirukkural video", shape: '2 couplets, each with its Tamil meaning.',
    script: 'Bundled Thirukkural (offline, no model)', dateLabel: 'Daily edition date', generate: 'Generate 2 couplets in Tamil', details: 'Couplet and meaning',
    note: 'Two couplets a day with the standard Tamil explanation, from the full public-domain Thirukkural bundled inside the app — no internet and no language model needed. Only the Virtue and Wealth sections (kurals 1-1080) are used, so the channel stays family friendly. The daily pair never repeats for 540 days.' },
  'english': { label: 'Spoken English', file: 'spoken-english', createTitle: "Create today's Spoken English video", shape: '3 everyday phrases, each with Tamil meaning.',
    script: 'Curated Tamil English lesson (offline)', dateLabel: 'Daily edition date', generate: 'Generate 3 English phrases', details: 'Phrase reference',
    note: 'Three practical English phrases a day with their Tamil meaning and an example sentence, in a friendly spoken-English class style. Curated catalog, fully offline; the daily line-up never repeats for 1,140 days.' },
  'gk': { label: 'Amazing Facts', file: 'amazing-facts', createTitle: "Create today's Amazing Facts video", shape: '3 general-knowledge facts in Tamil.',
    script: 'Curated Tamil facts (offline)', dateLabel: 'Daily edition date', generate: 'Generate 3 amazing facts', details: 'Fact reference',
    note: 'Three evergreen, checkable general-knowledge facts a day in simple spoken Tamil. Curated catalog, fully offline; the daily line-up never repeats for 1,140 days.' },
  'health': { label: 'Health Tips', file: 'health-tips', createTitle: "Create today's Health Tips video", shape: '3 safe wellbeing tips in Tamil.',
    script: 'Curated Tamil health tips (offline)', dateLabel: 'Daily edition date', generate: 'Generate 3 health tips', details: 'Tip reference',
    note: 'Three simple, widely accepted everyday wellbeing tips a day — food, sleep, movement, hygiene and mind — in spoken Tamil. Curated catalog, fully offline; the daily line-up never repeats for 1,140 days.' },
  'motivation': { label: 'Life Lessons', file: 'life-lessons', createTitle: "Create today's Life Lessons video", shape: '3 short positive Tamil lessons.',
    script: 'Curated Tamil life lessons (offline)', dateLabel: 'Daily edition date', generate: 'Generate 3 life lessons', details: 'Lesson reference',
    note: 'Three short, positive, family-friendly life lessons a day — effort, discipline, resilience, values, money habits, learning and health. Curated catalog, fully offline; the daily line-up never repeats for 1,140 days.' },
  'kids': { label: 'Kids Learning', file: 'kids-learning', createTitle: "Create today's Kids Learning video", shape: '3 Tamil basics for kids.', script: 'Curated kids learning (offline)', dateLabel: 'Daily edition date', generate: 'Generate 3 kids items', details: 'Learning reference',
    note: 'Three simple, family-safe Tamil basics a day for young children — the twelve vowels (உயிர் எழுத்து), counting words ஒன்று–எட்டு, common animals and basic colours, each with a gentle example. Curated catalog, fully offline; the daily line-up never repeats for 7,140 days.' },
  'meesho': { label: 'Tamil Budget Finds', file: 'tamil-budget-finds', createTitle: "Create today's Tamil Budget Finds video", shape: '1 Meesho budget product: price, benefits, one honest caution and a tracked order link.',
    script: 'Meesho Finds catalogue (offline)', dateLabel: 'Daily product date', generate: 'Generate today’s product video', details: 'Product data',
    note: 'One budget product a day from the separate Meesho Finds catalogue. The video uses a product-image card, a Tamil price/benefit explanation, one honest caution and a tracked /go link. Add or edit products in Meesho Finds Admin. Strict affiliate mode blocks demo products from rendering or publishing. Affiliate disclosure is included in every caption.' },
};

export default function VideoCreator() {
  const [cap, setCap] = useState<Capabilities>();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<Kind>('history');
  const cfg = KINDS[kind];
  const [preview, setPreview] = useState<string | null>(null);
  const [day, setDay] = useState(new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kolkata', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date()));
  const [voice, setVoice] = useState('ta-IN-PallaviNeural');
  const [rate, setRate] = useState(15);
  const [pitch, setPitch] = useState(0);
  const [volume, setVolume] = useState(0);
  const [display, setDisplay] = useState<'tamil' | 'tanglish'>('tamil');
  const [voicing, setVoicing] = useState(false);
  const signed = (n: number) => (n >= 0 ? '+' : '') + n;
  const visibleJobs = jobs.filter(j => (j.kind || 'history') === kind);
  const job = visibleJobs.find(j => j.id === selected);
  const active = jobs.some(j => ['writing','rendering'].includes(j.status));
  const load = async () => { const r = await api.get<Envelope<Job[]>>('/video-creator/jobs'); setJobs(r.data.data); };
  useEffect(() => {
    void api.get<Envelope<Capabilities>>('/video-creator/capabilities').then(r=>setCap(r.data.data)).catch(e=>setError(errorMessage(e)));
    void load().catch(e=>setError(errorMessage(e)));
  }, []);
  useEffect(() => {
    // Poll faster while something is actively rendering, and always poll in the background
    // (slower) so a finished job's status -- and the Delete button it unlocks -- never stays
    // stuck just because this tab was left open past the last active render.
    const timer = window.setInterval(()=>{ void load().catch(e=>setError(errorMessage(e))); }, active ? 5000 : 20000);
    return ()=>window.clearInterval(timer);
  }, [active]);
  useEffect(()=>()=>{ if(preview?.startsWith('blob:')) URL.revokeObjectURL(preview); },[preview]);
  async function action(path: string, data = {}) {
    setBusy(true); setError(''); setSelected(undefined); setPreview(null);
    try {
      const r = await api.post<Envelope<Job>>(path, data);
      if ((r.data.data.kind || 'history') !== kind) throw new Error('Wrong video type returned. Restart the backend.');
      setSelected(r.data.data.id); await load();
    }
    catch(e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  async function previewVoice(v: string) {
    setVoicing(true);
    try {
      const r = await api.get('/voice/sample', { params: { voice: v, rate: signed(rate) + '%' }, responseType: 'blob' });
      await new Audio(URL.createObjectURL(r.data as Blob)).play();
    } catch { /* preview is best-effort */ } finally { setVoicing(false); }
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
  async function download(j: Job, saveFile = false, format: 'landscape' | 'portrait' = 'landscape') {
    setBusy(true); setError('');
    try {
      // Ask for a short-lived signed URL, then let the browser stream the MP4 to
      // disk/player. A blob + axios timeout fails on mobile for a 50 MB file.
      const r = await api.post(`/video-creator/jobs/${j.id}/download-link`, {format});
      const base = (api.defaults.baseURL || '/api/v1').replace(/\/+$/, '');
      const url = (/^https?:\/\//i.test(base) ? base : window.location.origin + base)
        + `/video-creator/download/${r.data.data.token}`;
      if (saveFile) window.location.assign(url);
      else { setSelected(j.id); setPreview(url); }
    }
    catch(e) {setError(errorMessage(e));} finally {setBusy(false);}
  }
  return (
    <section className="space-y-6 max-w-5xl">
      <h1 className="text-3xl font-bold">Video Creator</h1>
      <p>Ollama Tamil scripts · Neural Tamil narration · Background music · MP4 export</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
        <button disabled={busy} onClick={()=>{setKind('make-money');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-emerald-950 text-white p-8 w-full border border-lime-400">
          <span className="text-lime-300 text-sm">MONEY IDEAS · NATURAL TAMIL</span>
          <h2 className="text-2xl font-bold mt-2">HOW TO MAKE MONEY</h2>
          <p lang="ta" className="mt-3">தினமும் காசு சம்பாதிக்க 5 வழிகள் — தமிழில், ஒவ்வொன்றுக்கும் 4 வரிகள்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('news');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-sky-950 text-white p-8 w-full border border-sky-400">
          <span className="text-sky-300 text-sm">TAMIL NEWS · DAILY 10</span>
          <h2 className="text-2xl font-bold mt-2">DAILY NEWS</h2>
          <p lang="ta" className="mt-3">இன்றைய 10 முக்கிய செய்திகள் — RSS ஊடகங்களில் இருந்து, படம் + ஆதாரத்துடன்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('thirukkural');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-amber-950 text-white p-8 w-full border border-orange-400">
          <span className="text-orange-300 text-sm">CLASSIC WISDOM · DAILY 2 COUPLETS</span>
          <h2 className="text-2xl font-bold mt-2">THIRUKKURAL — தினம் ஒரு குறள்</h2>
          <p lang="ta" className="mt-3">தினமும் 2 திருக்குறள் — குறளும் அதன் தமிழ் விளக்கமும்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('english');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-cyan-950 text-white p-8 w-full border border-sky-400">
          <span className="text-sky-300 text-sm">LEARN ENGLISH · DAILY PHRASES</span>
          <h2 className="text-2xl font-bold mt-2">SPOKEN ENGLISH — DAILY PHRASES</h2>
          <p lang="ta" className="mt-3">தினமும் 3 ஆங்கில வாக்கியங்கள் — தமிழ் பொருளுடன்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('gk');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-violet-950 text-white p-8 w-full border border-fuchsia-400">
          <span className="text-fuchsia-300 text-sm">GENERAL KNOWLEDGE · DAILY FACTS</span>
          <h2 className="text-2xl font-bold mt-2">AMAZING FACTS — DAILY GK</h2>
          <p lang="ta" className="mt-3">தினமும் 3 அறிய தகவல்கள் — எளிய தமிழில்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('health');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-emerald-950 text-white p-8 w-full border border-emerald-400">
          <span className="text-emerald-300 text-sm">WELLBEING · DAILY TIPS</span>
          <h2 className="text-2xl font-bold mt-2">HEALTH TIPS — DAILY 3</h2>
          <p lang="ta" className="mt-3">தினமும் 3 உடல்நல குறிப்புகள் — எளிய தமிழில்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('motivation');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-slate-900 text-white p-8 w-full border border-amber-300">
          <span className="text-amber-300 text-sm">POSITIVE THINKING · DAILY LESSONS</span>
          <h2 className="text-2xl font-bold mt-2">LIFE LESSONS — DAILY 3</h2>
          <p lang="ta" className="mt-3">தினமும் 3 வாழ்க்கை பாடங்கள் — நேர்மறை சிந்தனை.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('kids');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-cyan-950 text-white p-8 w-full border border-cyan-300">
          <span className="text-cyan-300 text-sm">FOR CHILDREN · DAILY LEARNING</span>
          <h2 className="text-2xl font-bold mt-2">KIDS LEARNING — DAILY 3</h2>
          <p lang="ta" className="mt-3">குழந்தைகளுக்கு தினமும் 3 எளிய பாடங்கள் — எழுத்து, எண், விலங்கு, நிறம்.</p>
          <p className="mt-2">Click to create →</p>
        </button>
        <button disabled={busy} onClick={()=>{setKind('meesho');setOpen(true);setSelected(undefined);setPreview(null);}} className="flex-1 text-left rounded-xl bg-rose-950 text-white p-8 w-full border border-rose-400">
          <span className="text-rose-300 text-sm">AFFILIATE · TAMIL BUDGET FINDS</span>
          <h2 className="text-2xl font-bold mt-2">MEESHO FINDS — DAILY PRODUCT</h2>
          <p lang="ta" className="mt-3">தினமும் ஒரு budget product — விலை, நல்லது, கவனிக்க வேண்டியது, order link.</p>
          <p className="mt-2">Click to create →</p>
        </button>
      </div>
      {error && <p role="alert" className="bg-red-50 p-4 text-red-700">{error}</p>}
      {open && <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-bold text-xl">{cfg.createTitle}</h2>
        <p>{cfg.shape} Duration follows natural narration.</p>
        <p className="text-sm">Narrated text scenes with Tamil voice and BGM. Internet is required for neural speech.</p>
        {cfg.note && <p className="text-sm">{cfg.note}</p>}
        <p>Script: <b>{cfg.script || cap?.model || 'Checking…'}</b> {!cfg.script && cap && !cap.installed && '— not installed / Ollama unavailable'}</p>
        <label className="block">{cfg.dateLabel} <input type="date" value={day} onChange={e=>setDay(e.target.value)} className="border p-2 ml-3" /></label>
        <label className="block">Tamil voice <select value={voice} onChange={e=>setVoice(e.target.value)} className="border p-2 ml-3">{TAMIL_VOICES.map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select>
          <button type="button" onClick={()=>void previewVoice(voice)} disabled={voicing} className="ml-2 border rounded px-3 py-1.5 text-sm disabled:opacity-50">{voicing ? 'Playing…' : '🔊 Preview'}</button>
          <span className="block text-xs text-slate-500 mt-1">★ = best for an Indian Tamil audience. Preview any voice before rendering.</span>
        </label>
        <fieldset className="border rounded p-3 space-y-2">
          <legend className="text-sm font-bold px-1">Voice-over controls</legend>
          <label className="block text-sm">Speed ({signed(rate)}%) <input type="range" min={-50} max={50} step={5} value={rate} onChange={e=>setRate(+e.target.value)} className="ml-3 align-middle" /></label>
          <label className="block text-sm">Pitch ({signed(pitch)}Hz) <input type="range" min={-50} max={50} step={5} value={pitch} onChange={e=>setPitch(+e.target.value)} className="ml-3 align-middle" /></label>
          <label className="block text-sm">Volume ({signed(volume)}%) <input type="range" min={-50} max={50} step={5} value={volume} onChange={e=>setVolume(+e.target.value)} className="ml-3 align-middle" /></label>
          <p className="text-xs text-slate-500">Speed/Pitch/Volume adjust the Tamil voice reading it. 15% faster is the default; 0 = normal.</p>
        </fieldset>
        <fieldset className="border rounded p-3">
          <legend className="text-sm font-bold px-1">On-screen script</legend>
          <label className="mr-4 text-sm"><input type="radio" name="display" checked={display==='tamil'} onChange={()=>setDisplay('tamil')} className="mr-1" />Tamil script</label>
          <label className="text-sm"><input type="radio" name="display" checked={display==='tanglish'} onChange={()=>setDisplay('tanglish')} className="mr-1" />Tanglish (Latin letters)</label>
          <p className="text-xs text-slate-500 mt-1">Only changes on-screen captions — narration is always spoken in Tamil.</p>
        </fieldset>
        <button disabled={busy || active || !day || (!cfg.script && !cap?.installed)} onClick={()=>void action('/video-creator/jobs', {day,voice,kind,rate:signed(rate)+'%',pitch:signed(pitch)+'Hz',volume:signed(volume)+'%',display})} className="bg-teal-700 text-white rounded px-5 py-3 disabled:opacity-50">{cfg.generate}</button>
        <p className="text-sm">Local CPU generation can take several minutes. You can navigate away and return.</p>
      </div>}
      {jobs.length > 0 && <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-bold mb-3">Your videos</h2>
        <div className="flex flex-col sm:flex-row gap-2 overflow-x-auto">
          {visibleJobs.map(j=><div key={j.id} className="shrink-0 min-w-[200px] bg-slate-900 text-white rounded-lg p-4 flex flex-col">
            <div className="font-bold truncate">{KINDS[j.kind || 'history'].label}</div>
            <div className="text-xs text-amber-400 mt-1">{j.date}</div>
            <div className="text-xs mt-1">{j.status}</div>
            <button disabled={busy} onClick={()=>{setSelected(j.id);setPreview(null);}} className="text-teal-300 mt-2">View</button>
            {j.status === 'complete' && <div className="space-y-2 mt-2">
              <button disabled={busy} onClick={()=>void download(j, true)} className="bg-teal-700 text-white p-2 rounded">Download MP4</button>
              <ShareMenu />
            </div>}
            {j.status === 'failed' && <p className="text-[11px] mt-2 text-red-500">Generation failed — delete &amp; recreate.</p>}
            {(j.status === 'writing' || j.status === 'rendering') && <p className="text-[11px] mt-2 text-slate-400">Share button appears once the video is ready.</p>}
            <button disabled={busy || active} onClick={()=>void deleteJob(j.id)} className="text-red-400 text-xs mt-2 disabled:opacity-50">Delete</button>
          </div>)}
        </div>
        {visibleJobs.length === 0 && <p className="text-sm text-slate-500">No videos in this mode yet.</p>}
      </div>}
      {job && <article className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-bold text-xl">{KINDS[job.kind || 'history'].label} · {job.date} — {job.status}</h2>
        <p role="status">{job.message}</p>
        {job.points.map((p,i)=><div key={i} className="border-b pb-4"><h3 className="font-bold">{i+1}. {p.title_display || p.title || p.year}{p.title_en ? ` (${p.title_en})` : ''}</h3>{(p.lines_display || p.lines).map((l,n)=><p lang={p.lines_display ? undefined : 'ta'} key={n} className="my-2">{l}</p>)}<details><summary>{KINDS[job.kind || 'history'].details}</summary><p>{p.text}</p>{p.sections && <p>Section references: {p.sections}</p>}{(p.links||[]).map(l=><a key={l.link} href={l.link} target="_blank" rel="noreferrer" className="text-blue-700 block underline">{l.title}</a>)}</details></div>)}
        {job.status==='review' && <div>
          <p>Review the Tamil summaries against the linked sources before rendering.</p>
          <button disabled={busy || active} onClick={()=>void action(`/video-creator/jobs/${job.id}/render`)} className="bg-teal-700 text-white p-3 rounded disabled:opacity-50">Generate video with voice + clean text</button>
        </div>}
        {job.status==='complete' && <div className="space-y-3">
          <p>Duration: {job.duration} seconds</p>
          <button disabled={busy} onClick={()=>void download(job)} className="bg-teal-700 text-white p-3 rounded">Load video</button>
          <button disabled={busy} onClick={()=>void download(job, true)} className="bg-teal-700 text-white p-3 rounded ml-2">Download MP4</button>
          <ShareMenu />
          {preview && <video controls playsInline preload="metadata" src={preview} className="w-full rounded mt-2"/>}
          {job.media_sources && <details><summary>Photo credits / sources</summary>
            {job.media_sources.map(source=><p key={source.scene}>Scene {source.scene}: {source.provider === 'pexels' && source.source_url?.startsWith('https://www.pexels.com/') ? <a href={source.source_url} target="_blank" rel="noreferrer" className="underline">{source.photographer} / Pexels</a> : source.provider === 'feed' ? <a href={source.source_url} target="_blank" rel="noreferrer" className="underline">{(source as {publisher?: string}).publisher || 'Publisher'} RSS image</a> : source.provider === 'product' ? 'Product catalogue image' : 'Local illustration'}</p>)}
          </details>}
          {job.subtitles && <details><summary>Tamil subtitles ({job.subtitles.length} scenes)</summary>
            {job.subtitles.map((s,i)=><p key={i} className="text-sm">{s.start}s → {s.end}s: <span className="text-teal-300">{s.text}</span></p>)}
          </details>}
        </div>}
        {job.status!=='complete' && job.status!=='review' && <p className="text-sm text-slate-500">Pending generation…</p>}
      </article>}
    </section>
  );
}
