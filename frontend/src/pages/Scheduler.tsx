import { useEffect, useState } from 'react';
import { CalendarDays, Clock3, Plus, ArrowLeft, Check, Pause, Play, Pencil, Trash2, Youtube, Facebook, Instagram, Sparkles, FolderOpen } from 'lucide-react';
import { Link } from 'react-router-dom';
import api, { Envelope, errorMessage } from '../services/apiClient';
import { TAMIL_VOICES } from '../constants/voices';

type Frequency = 'daily' | 'weekly' | 'monthly' | 'custom';
interface FormData {
  name: string; project: string; run_time: string; frequency: Frequency;
  start_date: string; end_date: string; weekdays: number[]; month_day: number; interval_days: number;
  platforms: string[]; voice: string;
}
interface Task extends FormData {
  id: string; enabled: boolean; next_run: string | null; message: string; last_run?: string;
  last_job_status?: string; last_job_message?: string; publishing_status: string;
}
interface Project { id: string; name: string; description: string; kind?: 'video' | 'automation'; files?: string[] }
const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const channels = [{id:'youtube', name:'YouTube', Icon:Youtube, color:'text-red-600'}, {id:'facebook', name:'Facebook', Icon:Facebook, color:'text-blue-600'}, {id:'instagram', name:'Instagram', Icon:Instagram, color:'text-pink-600'}];
const inputClass = 'w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500';
function initialForm(): FormData {
  const today = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kolkata', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date());
  const end = new Date(today + 'T00:00:00Z'); end.setUTCDate(end.getUTCDate() + 30);
  return {name:'', project:'history', run_time:'08:00', frequency:'daily', start_date:today, end_date:end.toISOString().slice(0,10), weekdays:[0], month_day:1, interval_days:2, platforms:[], voice:'ta-IN-PallaviNeural'};
}
function repeatText(data: FormData) {
  if(data.frequency === 'weekly') return `Every ${data.weekdays.map(d=>weekdays[d]).join(', ') || 'selected weekday'}`;
  if(data.frequency === 'monthly') return `Monthly on day ${data.month_day}`;
  if(data.frequency === 'custom') return `Every ${data.interval_days} days`;
  return 'Every day';
}
function displayTime(value: string) { return new Intl.DateTimeFormat('en-IN', {timeZone:'Asia/Kolkata', day:'numeric', month:'short', year:'numeric', hour:'numeric', minute:'2-digit'}).format(new Date(value)); }

export default function Scheduler() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<FormData>(initialForm);
  const [editing, setEditing] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState('all');
  const load = async (isAlive?: () => boolean) => { const result = await api.get<Envelope<Task[]>>('/scheduler'); if (!isAlive || isAlive()) setTasks(result.data.data); };
  const loadProjects = async (isAlive?: () => boolean) => { const result = await api.get<Envelope<Project[]>>('/scheduler/projects'); if (!isAlive || isAlive()) setProjects(result.data.data); };
  useEffect(()=>{
    let alive = true;
    const refresh = async () => {
      const [tasksResult, projectsResult] = await Promise.allSettled([load(()=>alive), loadProjects(()=>alive)]);
      if (!alive) return;
      const failure = tasksResult.status === 'rejected' ? tasksResult.reason : projectsResult.status === 'rejected' ? projectsResult.reason : null;
      if (failure) setError(errorMessage(failure));
    };
    void refresh().finally(()=>{if(alive)setLoading(false);});
    const timer = window.setInterval(()=>void refresh(),20000);
    return ()=>{alive=false;window.clearInterval(timer);};
  },[]);
  function update<K extends keyof FormData>(key: K, value: FormData[K]) { setForm(prev=>({...prev,[key]:value})); }
  function openForm(task?: Task) {
    setEditing(task?.id || null); setError(''); setNotice('');
    setForm(task ? {name:task.name, project:task.project, run_time:task.run_time, frequency:task.frequency, start_date:task.start_date, end_date:task.end_date, weekdays:[...task.weekdays], month_day:task.month_day, interval_days:task.interval_days, platforms:[...task.platforms], voice:task.voice} : initialForm());
    setShowForm(true);
  }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setError('');
    if(form.end_date < form.start_date) {setError('End date must be on or after the start date.');return;}
    if(form.frequency === 'weekly' && !form.weekdays.length) {setError('Select at least one weekday.');return;}
    setBusy(true);
    try {
      if(editing) await api.put(`/scheduler/${editing}`,form); else await api.post('/scheduler',form);
      setShowForm(false); setNotice('Task saved. Scheduled videos will appear in your gallery.'); await load();
    } catch(e){setError(errorMessage(e));} finally {setBusy(false);}
  }
  async function action(task: Task, command: 'pause'|'resume'|'delete') {
    if(command === 'delete' && !window.confirm(`Delete schedule "${task.name}"? Generated videos will stay in your gallery.`))return;
    setBusy(true);setError('');setNotice('');
    try {
      if(command === 'delete') await api.delete(`/scheduler/${task.id}`); else await api.post(`/scheduler/${task.id}/${command}`);
      await load();
    }catch(e){setError(errorMessage(e));}finally{setBusy(false);}
  }
  const enabled = tasks.filter(t=>t.enabled && t.next_run);
  const visible = tasks.filter(t=>filter==='all' || (filter==='active' ? t.enabled && t.next_run : !t.enabled));
  const next = enabled.map(t=>t.next_run!).sort()[0];
  const currentProject = projects.find(p=>p.id===form.project);
  const isAutomation = currentProject?.kind === 'automation';
  const groups = { video: projects.filter(p=>p.kind!=='automation'), automation: projects.filter(p=>p.kind==='automation') };
  return <section className="max-w-6xl mx-auto space-y-6 pb-12">
    <header className="rounded-2xl bg-slate-900 p-6 sm:p-8 text-white flex flex-col sm:flex-row sm:items-center justify-between gap-5">
      <div><p className="text-teal-300 text-xs font-bold tracking-widest uppercase mb-2">Creator workspace / Automation</p><h1 className="text-3xl font-bold">Task Scheduler</h1><p className="text-slate-300 mt-2">Your projects. Your schedule. A consistent content routine.</p></div>
      {!showForm && <button disabled={loading || busy || !projects.length} onClick={()=>openForm()} className="inline-flex items-center justify-center gap-2 bg-teal-400 text-slate-950 font-bold rounded-xl px-5 py-3 disabled:opacity-50"><Plus size={20}/> New Task</button>}
      {showForm && <button disabled={busy} onClick={()=>setShowForm(false)} className="flex items-center gap-2 text-white"><ArrowLeft size={18}/> Back to tasks</button>}
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 text-red-800 p-4">{error}</div>}
    {notice && <p role="status" className="rounded-xl bg-teal-50 text-teal-800 p-4">{notice}</p>}
    {showForm ? <form onSubmit={save} className="grid lg:grid-cols-3 gap-6 items-start">
      <div className="lg:col-span-2 space-y-6">
        <section className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 space-y-5">
          <h2 className="font-bold text-xl flex items-center gap-3"><span className="rounded-lg bg-teal-50 text-teal-700 px-3 py-1">01</span> Project details</h2>
          <label className="block text-sm font-medium">Task name<input autoFocus required maxLength={100} value={form.name} onChange={e=>update('name',e.target.value)} placeholder="Morning Tamil history" className={`${inputClass} mt-2`}/></label>
          <label className="block text-sm font-medium">Project<select required value={form.project} onChange={e=>update('project',e.target.value)} className={`${inputClass} mt-2`}>
            {groups.video.length>0 && <optgroup label="Content videos">{groups.video.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>}
            {groups.automation.length>0 && <optgroup label="Playwright automation">{groups.automation.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</optgroup>}
          </select></label>
          <p className="text-sm text-slate-500">{currentProject?.description}</p>
          {isAutomation && <p className="rounded-xl bg-indigo-50 text-indigo-900 p-3 text-sm">Runs the project's <b>main.py</b> with Playwright (Python) on this PC. Video voice and share destinations below do not apply.</p>}
          {!isAutomation && <><label className="block text-sm font-medium">Tamil voice<select value={form.voice} onChange={e=>update('voice',e.target.value)} className={`${inputClass} mt-2`}>{TAMIL_VOICES.map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select></label></>}
        </section>
        <section className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 space-y-5">
          <h2 className="font-bold text-xl flex items-center gap-3"><span className="rounded-lg bg-teal-50 text-teal-700 px-3 py-1">02</span> Schedule & date range</h2>
          <fieldset><legend className="text-sm font-medium mb-2">Repeat</legend><div className="grid grid-cols-2 sm:grid-cols-4 gap-2">{(['daily','weekly','monthly','custom'] as Frequency[]).map(f=><button key={f} type="button" aria-pressed={form.frequency===f} onClick={()=>update('frequency',f)} className={`capitalize rounded-xl border py-3 font-medium ${form.frequency===f?'bg-teal-700 text-white border-teal-700':'bg-white text-slate-600 border-slate-200'}`}>{f}</button>)}</div></fieldset>
          {form.frequency==='weekly' && <fieldset><legend className="text-sm mb-2">Run on</legend><div className="flex flex-wrap gap-2">{weekdays.map((d,i)=><label key={d} className="border rounded-lg p-2 flex items-center gap-2"><input type="checkbox" checked={form.weekdays.includes(i)} onChange={()=>update('weekdays',form.weekdays.includes(i)?form.weekdays.filter(n=>n!==i):[...form.weekdays,i].sort())}/>{d}</label>)}</div></fieldset>}
          {form.frequency==='monthly' && <div><label className="block text-sm">Day of month<input type="number" min={1} max={31} required value={form.month_day} onChange={e=>update('month_day',Number(e.target.value))} className={`${inputClass} mt-2`}/></label><p className="text-xs text-slate-500 mt-2">For shorter months, runs on the last day of the month.</p></div>}
          {form.frequency==='custom' && <label className="block text-sm">Repeat every (days)<input type="number" min={1} max={365} required value={form.interval_days} onChange={e=>update('interval_days',Number(e.target.value))} className={`${inputClass} mt-2`}/><span className="text-xs text-slate-500">Counted from the start date.</span></label>}
          <div className="grid sm:grid-cols-2 gap-4"><label className="text-sm font-medium">Generation time<input type="time" required value={form.run_time} onChange={e=>update('run_time',e.target.value)} className={`${inputClass} mt-2`}/></label><div className="rounded-xl bg-slate-50 p-4 text-sm"><Clock3 size={18} className="text-teal-700 mb-1"/>Asia/Kolkata (IST)<p className="text-slate-500">UTC +05:30 · All task times</p></div></div>
          <div className="grid sm:grid-cols-2 gap-4"><label className="text-sm font-medium">Start date<input type="date" required value={form.start_date} onChange={e=>update('start_date',e.target.value)} className={`${inputClass} mt-2`}/></label><label className="text-sm font-medium">End date<input type="date" required min={form.start_date} value={form.end_date} onChange={e=>update('end_date',e.target.value)} className={`${inputClass} mt-2`}/></label></div>
        </section>
        {!isAutomation && <section className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 space-y-5">
          <h2 className="font-bold text-xl flex items-center gap-3"><span className="rounded-lg bg-teal-50 text-teal-700 px-3 py-1">03</span> Share destinations</h2>
          <div className="grid sm:grid-cols-3 gap-3">{channels.map(({id,name,Icon,color})=><label key={id} className={`rounded-xl border p-4 cursor-pointer flex items-center gap-3 ${form.platforms.includes(id)?'border-teal-500 bg-teal-50':'border-slate-200'}`}><input type="checkbox" checked={form.platforms.includes(id)} onChange={()=>update('platforms',form.platforms.includes(id)?form.platforms.filter(p=>p!==id):[...form.platforms,id])}/><Icon className={color} size={22}/><span className="font-medium text-sm">{name}</span></label>)}</div>
          <p className="rounded-xl bg-amber-50 text-amber-900 p-3 text-sm">Selections are saved as publishing preferences. Automatic posting needs official account connections, which are not configured yet. Scheduled videos are generated and saved to your gallery.</p>
        </section>}
      </div>
      <aside className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5 lg:sticky lg:top-6">
        <div className="flex items-center gap-2 font-bold text-lg"><Sparkles className="text-teal-600" size={20}/> Task preview</div>
        <h3 className="text-xl font-bold break-words">{form.name || 'Your new task'}</h3>
        <p className="text-sm text-slate-600">{projects.find(p=>p.id===form.project)?.name}</p>
        <div className="bg-slate-50 rounded-xl p-4 space-y-2"><p className="font-bold text-2xl">{form.run_time || '--:--'} <span className="text-xs font-normal">IST</span></p><p className="text-sm">{repeatText(form)}</p><p className="text-xs text-slate-500">{form.start_date} → {form.end_date}</p></div>
        <p className="text-sm flex gap-2"><Check size={18} className="text-teal-600 shrink-0"/>{isAutomation ? 'Runs main.py with Playwright and records the result.' : 'Generate script, narration, photos and MP4 automatically.'}</p>
        <p className="text-sm text-slate-500">{isAutomation ? 'Output log is saved under the automation runs.' : (form.platforms.length ? `${form.platforms.length} destinations selected · connection required` : 'Save to gallery only')}</p>
        <p className="text-xs text-slate-500">{isAutomation ? 'PC/backend must stay running. One automation run at a time; busy tasks wait.' : 'PC/backend must stay running. One video at a time; busy tasks wait. Missed prior days are skipped after restart.'}</p>
        <button disabled={busy} type="submit" className="w-full bg-teal-700 text-white font-bold rounded-xl py-3 disabled:opacity-50">{busy?'Saving…':editing?'Save changes':'Create task'}</button>
        <button disabled={busy} type="button" onClick={()=>setShowForm(false)} className="w-full text-slate-500">Cancel</button>
      </aside>
    </form> : <>
      <div className="grid sm:grid-cols-3 gap-4">{[{label:'Total tasks',value:tasks.length,Icon:CalendarDays},{label:'Active schedules',value:enabled.length,Icon:Play},{label:'Next generation · IST',value:next?displayTime(next):'No upcoming run',Icon:Clock3}].map(({label,value,Icon})=><div key={label} className="bg-white border rounded-2xl p-5"><Icon size={20} className="text-teal-600 mb-3"/><p className="text-sm text-slate-500">{label}</p><p className="font-bold text-xl mt-1">{value}</p></div>)}</div>
      <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex gap-2">{['all','active','paused'].map(f=><button key={f} aria-pressed={filter===f} onClick={()=>setFilter(f)} className={`rounded-full px-4 py-2 capitalize text-sm ${filter===f?'bg-slate-900 text-white':'bg-white border text-slate-600'}`}>{f}</button>)}</div><Link to="/video-creator" className="text-teal-700 text-sm underline">Open video gallery →</Link></div>
      {loading && <p role="status">Loading your schedules…</p>}
      {!loading && !visible.length && <div className="rounded-2xl border border-dashed bg-white py-16 text-center"><FolderOpen className="mx-auto text-teal-600 mb-4" size={40}/><h2 className="font-bold text-xl">{tasks.length?'No tasks in this view':'Plan your first video'}</h2><p className="text-slate-500 mt-2">Choose a project and let your content routine run on schedule.</p><button disabled={!projects.length} onClick={()=>openForm()} className="mt-5 text-teal-700 font-bold">+ Create your first task</button></div>}
      <div className="grid gap-4">{visible.map(task=><article key={task.id} className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 space-y-4">
        <div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-bold text-xl break-words">{task.name}</h2><p className="text-slate-500 text-sm mt-1">{projects.find(p=>p.id===task.project)?.name || task.project}</p></div><span className={`self-start text-xs rounded-full px-3 py-1 ${!task.enabled?'bg-slate-100 text-slate-600':task.next_run?'bg-teal-50 text-teal-700':'bg-blue-50 text-blue-700'}`}>{!task.enabled?'Paused':task.next_run?'Active':'Finished'}</span></div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm"><span className="flex items-center gap-2"><Clock3 size={16}/>{task.run_time} IST</span><span>{repeatText(task)}</span><span className="text-slate-500">{task.start_date} → {task.end_date}</span></div>
        <p className="text-sm">Next run: <b>{task.enabled && task.next_run ? displayTime(task.next_run) : '—'}</b></p>
        <div className="flex flex-wrap gap-2">{task.platforms.length?task.platforms.map(p=><span key={p} className="capitalize text-xs bg-amber-50 text-amber-900 rounded px-2 py-1">{p} · connection required</span>):<span className="text-xs text-slate-500">Gallery only</span>}</div>
        <p className="text-sm text-slate-500">{task.last_job_status?`Last video: ${task.last_job_status} — ${task.last_job_message || ''}`:task.message}</p>
        <div className="flex flex-wrap gap-4 border-t pt-4"><button disabled={busy} onClick={()=>openForm(task)} className="flex items-center gap-2 text-sm text-slate-700"><Pencil size={16}/> Edit</button><button disabled={busy} onClick={()=>void action(task,task.enabled?'pause':'resume')} className="flex items-center gap-2 text-sm text-teal-700">{task.enabled?<Pause size={16}/>:<Play size={16}/>} {task.enabled?'Pause':'Resume'}</button><button disabled={busy} onClick={()=>void action(task,'delete')} className="flex items-center gap-2 text-sm text-red-600 ml-auto"><Trash2 size={16}/> Delete task</button></div>
      </article>)}</div>
    </>}
  </section>;
}
