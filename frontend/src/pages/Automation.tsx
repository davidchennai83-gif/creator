import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Code2, FolderOpen, Play, Save, Trash2, Plus, Loader2, TerminalSquare, Clock3, FileCode2 } from 'lucide-react';
import api, { Envelope, errorMessage } from '../services/apiClient';

interface Project { name: string; files: string[]; modified: string }
interface Run {
  id: string; project: string; file: string; status: string; message: string;
  started_at: string | null; finished_at: string | null; exit_code: number | null; preview: string;
}
interface EditorState { project: string; file: string; content: string }

const inputClass = 'w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500';
const statusBadge = (status: string) => {
  const styles: Record<string, string> = {
    running: 'bg-blue-50 text-blue-700',
    completed: 'bg-teal-50 text-teal-700',
    failed: 'bg-red-50 text-red-700',
    waiting: 'bg-amber-50 text-amber-900',
  };
  return (styles[status] || 'bg-slate-100 text-slate-600');
};

export default function Automation() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [newName, setNewName] = useState('');
  const [newFile, setNewFile] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const polling = useRef(false);

  const loadProjects = useCallback(async () => {
    const result = await api.get<Envelope<Project[]>>('/automation/projects');
    setProjects(result.data.data);
  }, []);
  const loadRuns = useCallback(async () => {
    const result = await api.get<Envelope<Run[]>>('/automation/runs');
    setRuns(result.data.data);
    return result.data.data;
  }, []);

  useEffect(() => {
    let alive = true;
    Promise.all([api.get<Envelope<Project[]>>('/automation/projects'), api.get<Envelope<Run[]>>('/automation/runs')])
      .then(([a, b]) => { if (alive) { setProjects(a.data.data); setRuns(b.data.data); } })
      .catch(e => { if (alive) setError(errorMessage(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const anyRunning = runs.some(r => r.status === 'running');
    if (!anyRunning || polling.current) return;
    polling.current = true;
    let failures = 0;
    const timer = window.setInterval(async () => {
      const next = await loadRuns().catch(() => null);
      if (next) {
        failures = 0;
        const busy = next.some(r => r.status === 'running');
        const latest = next[0];
        if (latest && (latest.status === 'completed' || latest.status === 'failed')) setOutput(latest.preview || latest.message);
        if (!busy) { polling.current = false; window.clearInterval(timer); }
      } else if (++failures >= 15) {
        polling.current = false;
        window.clearInterval(timer);
        setError('Lost connection to the automation runner. Reload to resume live updates.');
      }
    }, 2000);
    return () => { polling.current = false; window.clearInterval(timer); };
  }, [runs, loadRuns]);

  async function createProject(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.post<Envelope<Project>>('/automation/projects', { name: newName.trim() });
      setNewName(''); setNotice(`Project "${result.data.data.name}" created with a template main.py.`);
      await loadProjects();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function openFile(project: string, file: string) {
    setError(''); setNotice('');
    try {
      const result = await api.get<Envelope<{ name: string; content: string }>>(`/automation/projects/${encodeURIComponent(project)}/files/${encodeURIComponent(file)}`);
      setEditor({ project, file, content: result.data.data.content });
    } catch (e) { setError(errorMessage(e)); }
  }

  async function saveFile() {
    if (!editor) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.post(`/automation/projects/${encodeURIComponent(editor.project)}/files`, { name: editor.file, content: editor.content });
      setNotice(`Saved ${editor.file}.`);
      await loadProjects();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function addFile(event: React.FormEvent) {
    event.preventDefault(); if (!editor?.project || !newFile.trim()) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.post(`/automation/projects/${encodeURIComponent(editor.project)}/files`, { name: newFile.trim(), content: '' });
      setNewFile('');
      await loadProjects();
      await openFile(editor.project, newFile.trim());
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function runFile(file: string) {
    if (!editor) return;
    setBusy(true); setError(''); setNotice(''); setOutput('Starting run…');
    try {
      await api.post<Envelope<Run>>(`/automation/projects/${encodeURIComponent(editor.project)}/run`, { file });
      setOutput('Run started. Waiting for output…');
      await loadRuns();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  async function deleteProject(project: string) {
    if (!window.confirm(`Delete project "${project}" and all its files?`)) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.delete(`/automation/projects/${encodeURIComponent(project)}`);
      if (editor?.project === project) setEditor(null);
      setNotice(`Deleted project "${project}".`);
      await loadProjects();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }

  return <section className="max-w-6xl mx-auto space-y-6 pb-12">
    <header className="rounded-2xl bg-slate-900 p-6 sm:p-8 text-white flex flex-col sm:flex-row sm:items-center justify-between gap-5">
      <div><p className="text-teal-300 text-xs font-bold tracking-widest uppercase mb-2">Creator workspace / Recorder</p><h1 className="text-3xl font-bold">Automation</h1><p className="text-slate-300 mt-2">Playwright projects that run on your machine — standalone or on the Task Scheduler.</p></div>
      <span className="inline-flex items-center gap-2 rounded-xl bg-teal-400 text-slate-950 font-bold px-4 py-2"><Bot size={18}/> Playwright</span>
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 text-red-800 p-4">{error}</div>}
    {notice && <p role="status" className="rounded-xl bg-teal-50 text-teal-800 p-4">{notice}</p>}
    <div className="grid lg:grid-cols-3 gap-4">{[{label:'Projects',value:projects.length,Icon:FolderOpen},{label:'Script files',value:projects.reduce((n,p)=>n+p.files.length,0),Icon:FileCode2},{label:'Recent runs',value:runs.length,Icon:Clock3}].map(({label,value,Icon})=><div key={label} className="bg-white border rounded-2xl p-5"><Icon size={20} className="text-teal-600 mb-3"/><p className="text-sm text-slate-500">{label}</p><p className="font-bold text-xl mt-1">{value}</p></div>)}</div>
    {loading && <p role="status">Loading your projects…</p>}
    {!loading && !projects.length && <div className="rounded-2xl border border-dashed bg-white py-16 text-center"><Bot className="mx-auto text-teal-600 mb-4" size={40}/><h2 className="font-bold text-xl">No automation projects yet</h2><p className="text-slate-500 mt-2">Create one below and we'll scaffold a working Playwright script.</p></div>}
    <form onSubmit={createProject} className="bg-white rounded-2xl border border-slate-200 p-5 flex flex-col sm:flex-row gap-3">
      <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Project name, e.g. Morning stock check" required maxLength={60} className={`${inputClass} flex-1`}/>
      <button disabled={busy} className="inline-flex items-center justify-center gap-2 bg-teal-700 text-white font-bold rounded-xl px-5 py-3 disabled:opacity-50"><Plus size={20}/> New project</button>
    </form>
    <div className="grid lg:grid-cols-3 gap-6 items-start">
      <div className="space-y-4">
        {projects.map(project => <article key={project.name} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-bold break-words">{project.name}</h2>
            <button title="Delete project" disabled={busy} onClick={()=>void deleteProject(project.name)} className="text-red-600 disabled:opacity-50"><Trash2 size={16}/></button>
          </div>
          <p className="text-xs text-slate-500">Modified {project.modified}</p>
          <div className="flex flex-wrap gap-2">{project.files.map(file => <button key={file} disabled={busy} onClick={()=>void openFile(project.name, file)} className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs border ${editor?.project===project.name&&editor.file===file?'bg-teal-700 text-white border-teal-700':'bg-slate-50 border-slate-200 text-slate-600'} `}><Code2 size={13}/>{file}</button>)}</div>
        </article>)}
      </div>
      <div className="lg:col-span-2 space-y-4">
        {!editor ? <div className="rounded-2xl border border-dashed bg-white py-12 text-center text-slate-500">Select a project file on the left to view and edit it.</div> : <>
          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-bold flex items-center gap-2 break-all"><FileCode2 className="text-teal-600" size={18}/>{editor.project}/{editor.file}</h2>
              <div className="flex flex-wrap gap-2">
                <button disabled={busy} onClick={()=>void saveFile()} className="inline-flex items-center gap-2 bg-teal-700 text-white text-sm font-bold rounded-lg px-4 py-2 disabled:opacity-50"><Save size={16}/> Save</button>
                <button disabled={busy} onClick={()=>void runFile(editor.file)} className="inline-flex items-center gap-2 bg-slate-900 text-white text-sm font-bold rounded-lg px-4 py-2 disabled:opacity-50"><Play size={16}/> Run</button>
              </div>
            </div>
            <textarea value={editor.content} onChange={e=>setEditor({...editor, content: e.target.value})} spellCheck={false} className="w-full h-72 rounded-xl border border-slate-200 bg-slate-950 text-green-300 text-sm font-mono p-3 focus:outline-none focus:ring-2 focus:ring-teal-500" placeholder="# Playwright (Python) script…"/>
            <form onSubmit={addFile} className="flex flex-col sm:flex-row gap-2">
              <input value={newFile} onChange={e=>setNewFile(e.target.value)} placeholder="New script name, e.g. reports.py" className={`${inputClass} flex-1 !py-2 text-sm`}/>
              <button disabled={busy} className="text-teal-700 text-sm font-bold border border-teal-200 rounded-lg px-4 py-2 disabled:opacity-50">Add file</button>
            </form>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h2 className="font-bold flex items-center gap-2 mb-3"><TerminalSquare className="text-teal-600" size={18}/> Run output</h2>
            <pre className="rounded-xl bg-slate-950 text-green-300 text-xs font-mono p-3 overflow-auto max-h-64 whitespace-pre-wrap">{output || 'No run yet. Press Run to execute in Playwright.'}</pre>
            {runs.length > 0 && <div className="mt-4 space-y-2">
              {runs.map(run => <div key={run.id} className="flex flex-wrap items-center gap-3 text-sm border-t border-slate-100 pt-2">
                <span className="text-xs text-slate-500">{run.started_at?.slice(0,19).replace('T',' ') || '—'}</span>
                <b className="break-all">{run.project}/{run.file}</b>
                <span className={`rounded-full px-2 py-0.5 text-xs ${statusBadge(run.status)}`}>{run.status}</span>
                {run.status==='running' && <Loader2 size={14} className="animate-spin text-blue-600"/>}
                <span className="text-slate-500 text-xs flex-1 truncate">{run.message}</span>
              </div>)}
            </div>}
          </div>
        </>}
      </div>
    </div>
  </section>;
}