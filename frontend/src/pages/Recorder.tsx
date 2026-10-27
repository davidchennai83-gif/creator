import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Play, Square, Save, FilePlus2, Download, Trash2, RefreshCw, Copy, Bug, SkipForward, Eraser, CircleDot } from 'lucide-react';
import apiClient, { downloadBlob, errorMessage } from '../services/apiClient';
import { closeRecorderSocket, recorderSocket, RecorderAgent, RecorderEvent } from '../services/recorderSocket';
import { Toast } from '../components/common/Toast';

interface Recording {
  name: string;
  type: 'web' | 'desktop';
  size: number;
  modified: string;
}

interface ViewerFile {
  name: string;
  type: 'web' | 'desktop';
}

const LINE_HEIGHT = 18;

export default function Recorder() {
  const [agents, setAgents] = useState<RecorderAgent[]>([]);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Recording controls
  const [recordType, setRecordType] = useState<'web' | 'desktop'>('web');
  const [startUrl, setStartUrl] = useState('');
  const [appPath, setAppPath] = useState('');
  const [recordName, setRecordName] = useState('');
  const [recording, setRecording] = useState(false);
  const [recStatus, setRecStatus] = useState('');
  const [recLog, setRecLog] = useState<string[]>([]);

  // Code reviewer
  const [viewerFile, setViewerFile] = useState<ViewerFile | null>(null);
  const [code, setCode] = useState('');
  const [viewerStatus, setViewerStatus] = useState<{ text: string; tone: string }>({ text: '', tone: 'text-gray-400' });
  const [runLog, setRunLog] = useState<string[]>([]);
  const [breakpoints, setBreakpoints] = useState<Set<number>>(new Set());
  const [pausedLine, setPausedLine] = useState<number | null>(null);
  const [debugEnabled, setDebugEnabled] = useState(false);
  const [windowsUser, setWindowsUser] = useState('');

  const codeRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);
  // Maps a line in the injected (temp) script back to the line shown in the editor.
  const injectedLineMap = useRef<(number | null)[]>([]);

  const notify = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    if (type !== 'error') setTimeout(() => setToast(null), 3500);
  }, []);

  const lines = useMemo(() => (code ? code.split('\n') : ['']), [code]);

  const renderGutter = useCallback(() => {
    const gutter = gutterRef.current;
    const area = codeRef.current;
    if (!gutter) return;
    gutter.replaceChildren();
    for (let i = 1; i <= lines.length; i += 1) {
      const isBreakpoint = breakpoints.has(i);
      const isPaused = pausedLine === i;
      const row = document.createElement('button');
      row.type = 'button';
      row.dataset.line = String(i);
      row.className = 'block w-full text-right px-1.5 rounded font-mono text-xs leading-[18px] cursor-pointer select-none';
      row.style.color = isPaused ? '#fde047' : isBreakpoint ? '#fca5a5' : '#5a6072';
      if (isPaused) row.style.background = '#854d0e';
      else if (isBreakpoint) row.style.background = '#7f1d1d';
      row.textContent = `${isPaused ? '▶' : isBreakpoint ? '●' : ''}${i}`;
      row.onclick = () =>
        setBreakpoints((previous) => {
          const next = new Set(previous);
          if (next.has(i)) next.delete(i);
          else next.add(i);
          return next;
        });
      gutter.appendChild(row);
    }
    if (area) gutter.scrollTop = area.scrollTop;
  }, [breakpoints, lines.length, pausedLine]);

  useEffect(() => {
    renderGutter();
  }, [renderGutter]);

  // ── Data loaders ───────────────────────────────────────────────────────────
  const loadAgents = useCallback(async () => {
    try {
      const { data } = await apiClient.get<{ data: { agents: RecorderAgent[] } }>('/recorder/agents');
      setAgents(data.data.agents ?? []);
    } catch {
      setAgents([]);
    }
  }, []);

  const loadRecordings = useCallback(async () => {
    try {
      const { data } = await apiClient.get<{ data: { recordings: Recording[] } }>('/recorder/list');
      setRecordings(data.data.recordings ?? []);
    } catch (error) {
      notify(errorMessage(error), 'error');
    }
  }, [notify]);

  useEffect(() => {
    void loadAgents();
    void loadRecordings();
  }, [loadAgents, loadRecordings]);

  // ── Socket wiring ──────────────────────────────────────────────────────────
  useEffect(() => {
    const socket = recorderSocket();

    const onStatus = (payload: { agents?: RecorderAgent[] }) => {
      setAgents(payload.agents ?? []);
    };

    const onEvent = (data: RecorderEvent) => {
      const message = data.msg ?? '';
      setRecLog((previous) => [...previous, `[${new Date().toLocaleTimeString()}] ${message}`]);

      switch (data.type) {
        case 'started':
          setRecording(true);
          setRecStatus('Recording started…');
          break;
        case 'saved':
          setRecording(false);
          setRecStatus(`Saved: ${data.name ?? ''}`);
          notify(`Recording saved: ${data.name ?? ''}`, 'success');
          void loadRecordings();
          break;
        case 'error':
          setRecording(false);
          setRecStatus(`Error: ${message}`);
          notify(`Recorder: ${message}`, 'error');
          break;
        case 'run_started':
          setViewerStatus({ text: message, tone: 'text-yellow-300' });
          setRunLog([]);
          setPausedLine(null);
          setDebugEnabled(false);
          break;
        case 'run_output': {
          setRunLog((previous) => [...previous, message]);
          // pdb prints "> file(NNN)func()" immediately before pausing.
          const match = /\((\d+)\)[\w<>.]*\(\)\s*$/.exec(message.trim());
          if (match) {
            const injected = Number(match[1]);
            const original = injectedLineMap.current[injected - 1];
            if (original) {
              setPausedLine(original);
              const area = codeRef.current;
              const text = area?.value.split('\n') ?? [];
              let offset = 0;
              for (let i = 0; i < original - 1 && i < text.length; i += 1) offset += text[i].length + 1;
              area?.focus();
              area?.setSelectionRange(offset, offset + (text[original - 1] ?? '').length);
              if (area) area.scrollTop = Math.max(0, (original - 5) * LINE_HEIGHT);
            }
          }
          if (message.includes('(Pdb)')) {
            setViewerStatus({ text: '⏸ Paused at breakpoint — Step or Continue', tone: 'text-yellow-300' });
            setDebugEnabled(true);
          }
          break;
        }
        case 'debug_paused':
          setViewerStatus({ text: `⏸ ${message}`, tone: 'text-yellow-300' });
          setDebugEnabled(true);
          break;
        case 'run_finished':
          setViewerStatus({ text: message, tone: 'text-green-400' });
          notify(message, 'success');
          setDebugEnabled(false);
          setPausedLine(null);
          break;
        case 'run_error':
          setViewerStatus({ text: message, tone: 'text-red-400' });
          notify(message, 'error');
          setDebugEnabled(false);
          setPausedLine(null);
          break;
        default:
          break;
      }
    };

    socket.on('recorder_agent_status', onStatus);
    socket.on('recorder_event', onEvent);
    return () => {
      socket.off('recorder_agent_status', onStatus);
      socket.off('recorder_event', onEvent);
      closeRecorderSocket();
    };
  }, [loadRecordings, notify]);

  // ── Agent setup ────────────────────────────────────────────────────────────
  const agentCommand = useMemo(() => {
    const user = windowsUser.trim() || '<your-windows-username>';
    return [
      'pip install "python-socketio[client]" pynput pyautogui playwright',
      `cd C:\\Users\\${user}\\creator-platform\\backend\\recorder\\agent`,
      'python recorder_agent.py --hub http://127.0.0.1:8000',
    ].join('\n');
  }, [windowsUser]);

  // ── Recording actions ──────────────────────────────────────────────────────
  const startRecording = async () => {
    if (agents.length === 0) {
      notify('No recorder agent connected. Start recorder_agent.py on the machine you want to drive.', 'error');
      return;
    }
    const name = recordName.trim() || `recording_${new Date().toISOString().slice(0, 19).replace(/\W/g, '_')}`;
    setRecLog([]);
    setRecStatus('Starting recording…');
    try {
      await apiClient.post('/recorder/command', {
        cmd: 'start',
        sid: agents[0].sid,
        type: recordType,
        url: startUrl.trim(),
        app_path: appPath.trim(),
        name,
      });
    } catch (error) {
      notify(`Start failed: ${errorMessage(error)}`, 'error');
    }
  };

  const stopRecording = async () => {
    if (agents.length === 0) {
      notify('No agent connected', 'error');
      return;
    }
    setRecStatus('Stopping and saving…');
    try {
      await apiClient.post('/recorder/command', { cmd: 'stop', sid: agents[0].sid });
    } catch (error) {
      notify(`Stop failed: ${errorMessage(error)}`, 'error');
    }
  };

  // ── Code reviewer actions ──────────────────────────────────────────────────
  /** Insert a breakpoint() call before each flagged line, descending so the
   *  remaining line numbers stay valid. Returns the script to run. */
  const injectBreakpoints = (text: string): string => {
    const source = text.split('\n');
    const map: (number | null)[] = source.map((_, index) => index + 1);
    if (breakpoints.size === 0) {
      injectedLineMap.current = map;
      return text;
    }
    [...breakpoints].sort((a, b) => b - a).forEach((lineNumber) => {
      const index = lineNumber - 1;
      if (index < 0 || index > source.length) return;
      const indent = /^\s*/.exec(source[index] ?? '')?.[0] ?? '';
      source.splice(index, 0, `${indent}breakpoint()`);
      map.splice(index, 0, null);
    });
    injectedLineMap.current = map;
    return source.join('\n');
  };

  const newFile = () => {
    const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14);
    const name = `untitled_${stamp}.py`;
    setViewerFile({ name, type: 'web' });
    setCode('');
    setBreakpoints(new Set());
    setPausedLine(null);
    setViewerStatus({ text: '', tone: 'text-gray-400' });
    setRunLog([]);
    injectedLineMap.current = [];
    codeRef.current?.focus();
  };

  const viewFile = async (name: string) => {
    setViewerFile({ name, type: 'web' });
    setCode('Loading…');
    setBreakpoints(new Set());
    setViewerStatus({ text: '', tone: 'text-gray-400' });
    setRunLog([]);
    try {
      const { data } = await apiClient.get<{ data: { content: string; type: 'web' | 'desktop' } }>(
        `/recorder/content/${encodeURIComponent(name)}`,
      );
      setCode(data.data.content ?? '');
      setViewerFile({ name, type: data.data.type });
    } catch (error) {
      setCode(`Error loading file: ${errorMessage(error)}`);
    }
    injectedLineMap.current = [];
  };

  const saveFile = async () => {
    if (!viewerFile) return;
    setViewerStatus({ text: 'Saving…', tone: 'text-yellow-300' });
    try {
      await apiClient.post('/recorder/save-content', {
        name: viewerFile.name,
        type: viewerFile.type,
        content: code,
      });
      setViewerStatus({ text: 'Saved.', tone: 'text-green-400' });
      notify('Script saved', 'success');
      void loadRecordings();
    } catch (error) {
      setViewerStatus({ text: `Save failed: ${errorMessage(error)}`, tone: 'text-red-400' });
      notify(`Save failed: ${errorMessage(error)}`, 'error');
    }
  };

  const runFile = async () => {
    if (!viewerFile) return;
    if (agents.length === 0) {
      notify('No recorder agent connected. Start recorder_agent.py on your Windows machine.', 'error');
      return;
    }
    const isDebug = breakpoints.size > 0;
    setViewerStatus({
      text: isDebug ? 'Starting run (debug mode)…' : 'Starting run…',
      tone: 'text-yellow-300',
    });
    try {
      await apiClient.post('/recorder/run', {
        name: viewerFile.name,
        type: viewerFile.type,
        content: injectBreakpoints(code),
        debug: isDebug,
      });
      if (isDebug) setDebugEnabled(true);
    } catch (error) {
      setViewerStatus({ text: `Run failed: ${errorMessage(error)}`, tone: 'text-red-400' });
      notify(`Run failed: ${errorMessage(error)}`, 'error');
    }
  };

  const stopRun = async () => {
    if (agents.length === 0) {
      notify('No recorder agent connected.', 'error');
      return;
    }
    try {
      await apiClient.post('/recorder/stop-run', {});
      setViewerStatus({ text: 'Stopping…', tone: 'text-yellow-300' });
    } catch (error) {
      notify(`Stop failed: ${errorMessage(error)}`, 'error');
    }
  };

  const sendDebugInput = async (input: 'n' | 'c') => {
    try {
      await apiClient.post('/recorder/debug-input', { input });
    } catch (error) {
      notify(`Debugger command failed: ${errorMessage(error)}`, 'error');
    }
  };

  const removeRecording = async (name: string) => {
    if (!window.confirm(`Delete recording: ${name}?`)) return;
    try {
      await apiClient.post('/recorder/delete', { name, type: 'web' });
      notify('Deleted', 'success');
      void loadRecordings();
    } catch (error) {
      notify(errorMessage(error), 'error');
    }
  };

  const downloadRecording = async (name: string) => {
    try {
      await downloadBlob(`/recorder/download/${encodeURIComponent(name)}`, name);
    } catch (error) {
      notify(`Download failed: ${errorMessage(error)}`, 'error');
    }
  };

  const downloadAgent = async (filename: string) => {
    try {
      await downloadBlob(`/recorder/download-agent/${encodeURIComponent(filename)}`, filename);
    } catch (error) {
      notify(`Download failed: ${errorMessage(error)}`, 'error');
    }
  };

  const agentConnected = agents.length > 0;
  const panel = 'bg-gray-800 border border-gray-700 rounded-xl p-5';

  return (
    <section className="space-y-5">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <CircleDot size={24} /> Recorder
        </h1>
        <span
          className={`text-xs px-3 py-1.5 rounded-full border ${
            agentConnected ? 'text-green-400 border-green-800 bg-green-950/40' : 'text-red-400 border-red-900 bg-red-950/40'
          }`}
        >
          {agentConnected
            ? `● ${agents.length} agent(s) connected: ${agents.map((a) => a.hostname).join(', ')}`
            : '● No agent connected'}
        </span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)] gap-4 items-start">
        {/* ── Code Reviewer ─────────────────────────────────────────────── */}
        <div className={`${panel} min-w-0`}>
          <div className="flex flex-wrap justify-between items-center gap-2 mb-3">
            <h2 className="font-bold text-sm">
              Code Reviewer — <span className="text-gray-400 font-normal">{viewerFile?.name ?? 'no file open'}</span>
            </h2>
            <div className="flex flex-wrap gap-2">
              <SmallButton onClick={newFile} icon={<FilePlus2 size={13} />}>New</SmallButton>
              <SmallButton onClick={() => void saveFile()} icon={<Save size={13} />}>Save</SmallButton>
              <SmallButton onClick={() => void runFile()} icon={<Play size={13} />} tone="run">Run</SmallButton>
              <SmallButton onClick={() => void stopRun()} icon={<Square size={13} />} tone="stop">Stop</SmallButton>
              <SmallButton onClick={() => void sendDebugInput('n')} icon={<Bug size={13} />} disabled={!debugEnabled}
                title="Step to the next line (only active while paused at a breakpoint)">Step</SmallButton>
              <SmallButton onClick={() => void sendDebugInput('c')} icon={<SkipForward size={13} />} disabled={!debugEnabled}
                title="Continue until the next breakpoint">Continue</SmallButton>
              <SmallButton onClick={() => { setBreakpoints(new Set()); notify('Breakpoints cleared', 'success'); }}
                icon={<Eraser size={13} />}>Clear BPs</SmallButton>
            </div>
          </div>

          <p className="text-[11px] text-gray-400 mb-1">
            Click a line number to toggle a breakpoint. Run pauses there — use Step / Continue.
          </p>

          <div className="flex w-full h-[480px] max-h-[65vh] bg-gray-950 border border-gray-700 rounded-lg overflow-hidden">
            <div ref={gutterRef} className="shrink-0 h-full py-3 pr-1.5 bg-gray-900 border-r border-gray-700 overflow-hidden" />
            <textarea
              ref={codeRef}
              spellCheck={false}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onScroll={(e) => { if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop; }}
              placeholder="Click a file in Saved Recordings to view/edit, or click 'New' to write code here…"
              className="flex-1 min-w-0 h-full bg-gray-950 border-none p-3 font-mono text-xs text-lime-300 resize-none focus:outline-none"
            />
          </div>

          <p className={`mt-2.5 text-sm min-h-5 ${viewerStatus.tone}`}>{viewerStatus.text}</p>

          <h3 className="font-bold text-xs text-gray-400 mt-2.5 mb-1.5">Output</h3>
          <div className="bg-gray-950 rounded-lg p-2.5 font-mono text-xs text-sky-300 min-h-[120px] max-h-[260px] overflow-y-auto whitespace-pre-wrap">
            {runLog.length === 0 ? '' : runLog.join('\n')}
          </div>
        </div>

        {/* ── Right column ──────────────────────────────────────────────── */}
        <div className="min-w-0 space-y-4">
          <div className={panel}>
            <h2 className="font-bold mb-3 text-sm">Agent Setup</h2>
            <p className="text-sm text-gray-400 mb-3">Run this on the Windows machine you want to control:</p>
            <div className="mb-3 max-w-[280px]">
              <label className="block text-xs text-gray-400 mb-1">Windows Username</label>
              <input
                value={windowsUser}
                onChange={(e) => setWindowsUser(e.target.value)}
                placeholder="e.g. salmanf"
                className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm focus:outline-none"
              />
            </div>
            <pre className="bg-gray-950 rounded-lg p-3 font-mono text-xs text-lime-300 mb-3 whitespace-pre-line">
              {agentCommand}
            </pre>
            <div className="flex flex-wrap gap-2">
              <SmallButton onClick={() => {
                navigator.clipboard?.writeText(agentCommand)
                  .then(() => notify('Command copied to clipboard', 'success'))
                  .catch(() => notify('Copy failed, please copy manually', 'error'));
              }} icon={<Copy size={13} />}>Copy Command</SmallButton>
              <button type="button" onClick={() => void downloadAgent('Start_Recorder_Agent.bat')}
                className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded bg-blue-700 hover:bg-blue-600 text-white">
                <Download size={13} /> Installer (.bat)
              </button>
              <button type="button" onClick={() => void downloadAgent('recorder_agent.py')}
                className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white">
                <Download size={13} /> Agent (.py)
              </button>
              <SmallButton onClick={() => { void loadAgents(); notify('Agent status refreshed', 'info'); }}
                icon={<RefreshCw size={13} />}>Check Agent</SmallButton>
            </div>
            <p className="text-[11px] text-gray-500 mt-3">
              Recording and replay both run in a visible Chrome window over the DevTools port (9222) — never headless. If
              that port is closed the agent opens Chrome with its own profile folder, because Chrome 136+ blocks remote
              debugging on your everyday profile. That window is reused for every later recording and replay, so sign in
              to your accounts there once.
            </p>
          </div>

          <div className={panel}>
            <h2 className="font-bold mb-4 text-sm">Recording Controls</h2>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Type</label>
                <select value={recordType} onChange={(e) => setRecordType(e.target.value as 'web' | 'desktop')}
                  className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm focus:outline-none">
                  <option value="web">Web Browser (your open Chrome)</option>
                  <option value="desktop">Desktop / Windows App</option>
                </select>
              </div>
              {recordType === 'web' ? (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Start URL <span className="text-gray-500">(optional)</span></label>
                  <input value={startUrl} onChange={(e) => setStartUrl(e.target.value)} placeholder="https://…"
                    className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm min-w-[220px] focus:outline-none" />
                </div>
              ) : (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">App Path <span className="text-gray-500">(.lnk/.exe — auto-launches)</span></label>
                  <input value={appPath} onChange={(e) => setAppPath(e.target.value)}
                    placeholder="C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Excel.lnk"
                    className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm min-w-[280px] focus:outline-none" />
                </div>
              )}
              <div>
                <label className="block text-xs text-gray-400 mb-1">File Name</label>
                <input value={recordName} onChange={(e) => setRecordName(e.target.value)} placeholder="my_recording"
                  className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm min-w-[140px] focus:outline-none" />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button type="button" onClick={() => void startRecording()} disabled={recording}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-white text-sm disabled:opacity-40">
                <CircleDot size={14} /> Start Recording
              </button>
              <button type="button" onClick={() => void stopRecording()} disabled={!recording}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-700 hover:bg-red-600 text-white text-sm disabled:opacity-40">
                <Square size={14} /> Stop Recording
              </button>
            </div>
            <p className="mt-3 text-sm text-gray-400 min-h-5">{recStatus}</p>
            {recLog.length > 0 && (
              <pre className="mt-2.5 bg-gray-950 rounded-lg p-2.5 font-mono text-[11px] text-lime-300 max-h-[150px] overflow-y-auto whitespace-pre-wrap">
                {recLog.join('\n')}
              </pre>
            )}
          </div>

          <div className={panel}>
            <div className="flex justify-between items-center mb-3">
              <h2 className="font-bold text-sm">Saved Recordings</h2>
              <SmallButton onClick={() => void loadRecordings()} icon={<RefreshCw size={13} />}>Refresh</SmallButton>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-400 text-left border-b border-gray-700">
                    <th className="py-1.5 pr-2 font-medium">File Name</th>
                    <th className="py-1.5 pr-2 font-medium">Type</th>
                    <th className="py-1.5 pr-2 font-medium">Size</th>
                    <th className="py-1.5 pr-2 font-medium">Recorded</th>
                    <th className="py-1.5 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recordings.length === 0 ? (
                    <tr><td colSpan={5} className="text-center text-gray-400 py-6">No recordings yet.</td></tr>
                  ) : recordings.map((item) => (
                    <tr key={`${item.type}/${item.name}`} className="border-b border-gray-800 last:border-0">
                      <td className="py-1.5 pr-2">
                        <button type="button" onClick={() => void viewFile(item.name)}
                          className="text-sky-300 underline hover:text-sky-200 text-left break-all">{item.name}</button>
                      </td>
                      <td className="py-1.5 pr-2">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] ${
                          item.type === 'web' ? 'bg-blue-900 text-blue-200' : 'bg-green-900 text-green-200'}`}>
                          {item.type}
                        </span>
                      </td>
                      <td className="py-1.5 pr-2 text-gray-300">{(item.size / 1024).toFixed(1)} KB</td>
                      <td className="py-1.5 pr-2 text-gray-300">{item.modified}</td>
                      <td className="py-1.5">
                        <div className="flex gap-1">
                          <SmallButton onClick={() => void viewFile(item.name)}>View</SmallButton>
                          <SmallButton onClick={() => downloadRecording(item.name)} icon={<Download size={12} />}>Get</SmallButton>
                          <SmallButton onClick={() => void removeRecording(item.name)} icon={<Trash2 size={12} />}
                            tone="danger" title="Delete">Del</SmallButton>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SmallButton({
  children, onClick, icon, disabled, title, tone = 'default',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  icon?: React.ReactNode;
  disabled?: boolean;
  title?: string;
  tone?: 'default' | 'run' | 'stop' | 'danger';
}) {
  const tones = {
    default: 'bg-gray-700 hover:bg-gray-600 text-white',
    run: 'bg-green-700 hover:bg-green-600 text-white',
    stop: 'bg-red-700 hover:bg-red-600 text-white',
    danger: 'bg-gray-700 hover:bg-red-700 text-red-200',
  };
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded disabled:opacity-40 ${tones[tone]}`}>
      {icon}
      {children}
    </button>
  );
}
