"""
recorder_agent.py — Recorder Agent for Creator Platform (Windows)
=============================================================================
Runs on your local Windows machine and connects to Creator Platform over
Socket.IO. Two capture modes:

  * Desktop  — records mouse clicks / scroll / keypresses (pynput) and emits a
               PyAutoGUI script.
  * Web      — attaches to the Chrome window you ALREADY have open via the
               DevTools Protocol (CDP) and records what you do in it, then
               emits a Playwright script. No second browser, no headless mode.

The web mode deliberately does NOT use `playwright codegen`, which always opens
its own bundled Chromium. It uses connect_over_cdp() so recording happens in
your real, visible, already-running Chrome, with your real profile and logins.

Install:
    pip install "python-socketio[client]" pynput pyautogui playwright

Run:
    python recorder_agent.py --hub http://127.0.0.1:8000
    python recorder_agent.py --hub http://127.0.0.1:8000 --cli --no-relaunch-chrome

Note about Chrome 136+: Google refuses --remote-debugging-port on the *default*
profile. So web mode uses a dedicated, persistent profile directory
(%LOCALAPPDATA%\\CreatorRecorder\\chrome-profile) which keeps your logins and
tabs between runs. The first time, Chrome is relaunched into that profile.
"""

import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

try:
    import socketio
except ImportError:
    print("[ERROR] Install: pip install 'python-socketio[client]'")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────
DEFAULT_HUB = "http://127.0.0.1:8000"
AGENT_VERSION = "2.0.0"
CHROME_DEBUG_PORT = 9222
CHROME_PROFILE = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "CreatorRecorder" / "chrome-profile"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"),
]

# ── State ────────────────────────────────────────────────────────────────────
_recording = False
_record_type = None            # 'web' | 'desktop'
_record_name = ""              # filename chosen when recording started
_record_app_path = ""          # optional .lnk/.exe launched before a desktop recording
_events = []                   # desktop events
_start_time = None
_mouse_listener = None
_key_listener = None
_cdp = None                    # ChromeCdp instance while web-recording
_sio = socketio.Client()

_run_proc = None
_run_stopped_by_user = False
_run_lock = threading.Lock()
_run_stdin = None              # open pipe to a pdb-paused child process


def log(msg):
    print(f"[RECORDER] {msg}", flush=True)


def emit(event_type, msg="", **extra):
    payload = {"type": event_type, "msg": msg}
    payload.update(extra)
    if not _sio.connected:
        log(f"emit skipped (not connected): {event_type}")
        return
    try:
        _sio.emit("recorder_event", payload)
    except Exception as exc:  # socket may be mid-reconnect
        log(f"emit failed: {exc}")


def fmt_name():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ══════════════════════════════════════════════════════════════════════════════
# Desktop recording (pynput) — unchanged behaviour
# ══════════════════════════════════════════════════════════════════════════════
def start_desktop_recording(app_path=""):
    global _events, _mouse_listener, _key_listener, _start_time, _record_app_path

    try:
        from pynput import mouse, keyboard
    except ImportError:
        emit("error", "Install pynput: pip install pynput")
        return

    _record_app_path = app_path.strip().strip('"').strip("'")
    if _record_app_path:
        try:
            log(f"Launching app before recording: {_record_app_path}")
            os.startfile(_record_app_path)
            emit("action", f"Launched {_record_app_path} — waiting 3s for it to open...")
            time.sleep(3)
        except Exception as exc:
            emit("error", f"Could not launch app path: {exc}")

    _events = []
    _start_time = time.time()

    def on_click(x, y, button, pressed):
        if not _recording:
            return
        _events.append({
            "time": round(time.time() - _start_time, 3),
            "action": "click" if pressed else "release",
            "x": x, "y": y,
            "button": str(button).replace("Button.", ""),
        })
        emit("action", f"Click ({x},{y})")

    def on_scroll(x, y, dx, dy):
        if not _recording:
            return
        _events.append({
            "time": round(time.time() - _start_time, 3),
            "action": "scroll",
            "x": x, "y": y, "dx": dx, "dy": dy,
        })

    def on_press(key):
        if not _recording:
            return
        # pynput gives key.char = None (no exception) for combos like Ctrl+something.
        char = getattr(key, "char", None) or str(key).replace("Key.", "")
        _events.append({
            "time": round(time.time() - _start_time, 3),
            "action": "key_press",
            "key": char,
        })
        emit("action", f"Key: {char}")

    _mouse_listener = mouse.Listener(on_click=on_click, on_move=lambda *a: None, on_scroll=on_scroll)
    _key_listener = keyboard.Listener(on_press=on_press, on_release=lambda *a: None)
    _mouse_listener.start()
    _key_listener.start()
    log("Desktop recording started")


def stop_desktop_recording():
    global _mouse_listener, _key_listener
    for listener in (_mouse_listener, _key_listener):
        if listener:
            try:
                listener.stop()
            except Exception:
                pass
    _mouse_listener = None
    _key_listener = None
    log("Desktop recording stopped")


def generate_desktop_script(name):
    """Convert recorded desktop events to a PyAutoGUI script."""
    lines = [
        '"""',
        f"Desktop Recording: {name}",
        f"Recorded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Generated by Creator Platform Recorder",
        '"""',
        "",
        "import pyautogui",
        "import time",
    ]
    if _record_app_path:
        lines += ["import os", "", f"os.startfile({_record_app_path!r})", "time.sleep(3)"]
    lines += [
        "",
        # Recorded clicks can land on a screen edge (maximise/close/taskbar), which
        # trips PyAutoGUI's corner fail-safe even though these coordinates are
        # fixed and reviewed. Safe for a pre-recorded script.
        "pyautogui.FAILSAFE = False",
        "pyautogui.PAUSE = 0.1",
        "",
        "# ── Recorded Actions ──────────────────────────────────────────────────",
    ]
    previous = 0
    for event in _events:
        delay = round(event["time"] - previous, 3)
        if delay > 0.1:
            lines.append(f"time.sleep({delay})")
        previous = event["time"]
        if event["action"] == "click":
            button = "right" if event["button"] == "right" else "left"
            lines.append(f"pyautogui.click({event['x']}, {event['y']}, button='{button}')")
        elif event["action"] == "scroll":
            lines.append(f"pyautogui.scroll({event['dy']}, x={event['x']}, y={event['y']})")
        elif event["action"] == "key_press":
            key = event["key"]
            if not key:
                continue
            if len(key) == 1:
                lines.append(f"pyautogui.write({key!r})")
            else:
                lines.append(f"pyautogui.press({key.lower()!r})")
    lines += ["", "# ── End of Recording ─────────────────────────────────────────────────", ""]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Web recording — CDP attach to the Chrome you already have open
# ══════════════════════════════════════════════════════════════════════════════
_RECORDER_JS = r"""
(session) => {
  const KEY = '__crRecorder';
  const previous = window[KEY];
  if (previous && previous.session === session) { previous.flush(); return; }
  if (previous) previous.dispose();

  const queue = [];
  const flush = () => {
    if (typeof window.__crEmit !== 'function') return;
    while (queue.length) {
      const event = queue.shift();
      try { window.__crEmit(JSON.stringify(event)); }
      catch (e) { queue.unshift(event); return; }
    }
  };
  const push = (event) => { queue.push(event); flush(); };
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim().slice(0, 80);

  const cssEscape = (s) => (window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&'));
  const isUnique = (sel) => { try { return document.querySelectorAll(sel).length === 1; } catch (e) { return false; } };

  const cssPath = (el) => {
    if (el.id) { const s = '#' + cssEscape(el.id); if (isUnique(s)) return s; }
    for (const attr of ['data-testid', 'data-test', 'data-qa', 'data-cy']) {
      const v = el.getAttribute && el.getAttribute(attr);
      if (v) { const s = `[${attr}="${v}"]`; if (isUnique(s)) return s; }
    }
    if (el.name) { const s = `${el.tagName.toLowerCase()}[name="${el.name}"]`; if (isUnique(s)) return s; }
    const label = el.getAttribute && (el.getAttribute('aria-label') || el.getAttribute('placeholder'));
    if (label) { const s = `[aria-label="${label}"]`; if (isUnique(s)) return s; }

    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.id) { parts.unshift('#' + cssEscape(node.id)); break; }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = node.parentElement;
      if (node === document.body) break;
    }
    return parts.join(' > ');
  };

  const labelFor = (el) => {
    const aria = el.getAttribute && el.getAttribute('aria-label');
    if (aria) return clean(aria);
    return clean(el.innerText || el.value || el.placeholder || '');
  };

  const onClick = (e) => {
    const el = e.target;
    if (!el || el.nodeType !== 1) return;
    if (window[KEY]) window[KEY].seen.click++;
    push({ kind: 'click', selector: cssPath(el), text: labelFor(el), url: location.href });
  };
  const onChange = (e) => {
    const el = e.target;
    if (!el || el.nodeType !== 1) return;
    if (window[KEY]) window[KEY].seen.change++;
    const tag = el.tagName.toLowerCase();
    if (tag === 'input' && ['checkbox', 'radio'].includes(el.type)) {
      push({ kind: el.checked ? 'check' : 'uncheck', selector: cssPath(el), text: labelFor(el), url: location.href });
    } else if (tag === 'select') {
      const opt = el.options[el.selectedIndex];
      push({ kind: 'select', selector: cssPath(el), text: labelFor(el),
             value: el.value, label: opt ? clean(opt.text) : '', url: location.href });
    } else if (tag === 'textarea' || (tag === 'input' && !['checkbox','radio','submit','button','file'].includes(el.type))) {
      push({ kind: 'fill', selector: cssPath(el), text: labelFor(el), value: el.value, url: location.href });
    }
  };
  const onSubmit = (e) => { if (window[KEY]) window[KEY].seen.submit++; push({ kind: 'submit', selector: cssPath(e.target), text: labelFor(e.target), url: location.href }); };
  const onNavigate = () => { if (window[KEY]) window[KEY].seen.navigate++; push({ kind: 'navigate', url: location.href, text: '' }); };

  let scrollTimer = null;
  const onScroll = () => {
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      if (window[KEY]) window[KEY].seen.scroll++;
      push({ kind: 'scroll', x: Math.round(window.scrollX), y: Math.round(window.scrollY), url: location.href });
    }, 200);
  };

  document.addEventListener('click', onClick, true);
  document.addEventListener('change', onChange, true);
  document.addEventListener('submit', onSubmit, true);
  window.addEventListener('popstate', onNavigate);
  window.addEventListener('scroll', onScroll, true);

  // SPA route changes.
  if (!history.__crWrapped) {
    history.__crWrapped = true;
    for (const name of ['pushState', 'replaceState']) {
      const original = history[name];
      history[name] = function () {
        const result = original.apply(this, arguments);
        setTimeout(onNavigate, 0);
        return result;
      };
    }
  }

  // A dead __crEmit binding (agent restarted) must not swallow events: retry.
  const timer = setInterval(flush, 250);
  window[KEY] = {
    session,
    flush,
    push,
    pending: () => queue.length,
    seen: { click: 0, change: 0, submit: 0, navigate: 0, scroll: 0 },
    dispose() {
      clearInterval(timer);
      if (scrollTimer) clearTimeout(scrollTimer);
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('change', onChange, true);
      document.removeEventListener('submit', onSubmit, true);
      window.removeEventListener('popstate', onNavigate);
      window.removeEventListener('scroll', onScroll, true);
    },
  };

  push({ kind: 'ready', url: location.href, text: clean(document.title) });
}
"""


def _chrome_exe():
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _port_open(port, host="127.0.0.1", timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _devtools_ready(port, timeout=1.5):
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as response:
            return json.loads(response.read().decode()).get("Browser")
    except Exception:
        return None


def ensure_debuggable_chrome(relaunch=True, start_url="", timeout=25):
    """Make sure a debuggable Chrome is available, launching one if needed.

    Returns (browser_description, error). error is None on success.
    """
    browser = _devtools_ready(CHROME_DEBUG_PORT)
    if browser:
        return browser, None

    if not _port_open(CHROME_DEBUG_PORT):
        if not relaunch:
            return None, (
                f"Chrome is not listening on port {CHROME_DEBUG_PORT}. "
                "Start it with --remote-debugging-port, or allow relaunch."
            )
    else:
        # Something is on the port but it is not DevTools.
        return None, f"Port {CHROME_DEBUG_PORT} is in use by another program."

    exe = _chrome_exe()
    if not exe:
        return None, "Google Chrome was not found on this machine."

    CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={CHROME_PROFILE}",
    ]
    if start_url:
        args.append(start_url)
    log(f"Launching Chrome for recording: {' '.join(args)}")
    emit("action", "Chrome is being (re)launched with remote debugging enabled...")
    try:
        subprocess.Popen(args, close_fds=True)
    except Exception as exc:
        return None, f"Could not launch Chrome: {exc}"

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.5)
        browser = _devtools_ready(CHROME_DEBUG_PORT)
        if browser:
            return browser, None
    return None, (
        f"Chrome did not expose the DevTools port within {timeout}s. "
        "Close any other Chrome window on this profile and try again."
    )


class ChromeCdp:
    """Records interactions in the already-open Chrome over CDP."""

    def __init__(self, port=CHROME_DEBUG_PORT, timeout=30):
        self._pw = None
        self._browser = None
        self._context = None
        self._pages = []
        self._attached = set()
        self._lock = threading.Lock()
        self.events = []
        self.start_url = ""
        self._port = port
        self._timeout = timeout
        # New id per recording session, so a page left over from an earlier
        # agent run re-installs its listeners instead of feeding a dead binding.
        self.session = uuid.uuid4().hex
        self._cmds = queue.Queue()
        self._done = threading.Event()
        self._ready = threading.Event()
        self._error = None
        self._worker = threading.Thread(target=self._loop, name="cr-cdp", daemon=True)

    # -- worker thread: the sync Playwright API belongs to exactly one thread --
    def _loop(self):
        try:
            self._connect()
            while not self._done.is_set():
                try:
                    fn, args, kwargs = self._cmds.get(timeout=0.15)
                except queue.Empty:
                    # Any Playwright call pumps pending protocol events, which is
                    # what makes context.on("page") fire for tabs opened later.
                    self._pump()
                    continue
                try:
                    fn(*args, **kwargs)
                except Exception as exc:
                    log(f"cdp worker error in {getattr(fn, '__name__', fn)}: {exc}")
        except Exception as exc:
            self._error = str(exc)
        finally:
            try:
                if self._pw is not None:
                    self._pw.stop()
            except Exception:
                pass

    def _connect(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.connect_over_cdp(
            f"http://127.0.0.1:{self._port}", timeout=self._timeout * 1000,
        )
        contexts = [c for c in self._browser.contexts if c.pages] or self._browser.contexts
        if not contexts:
            raise RuntimeError(
                "Chrome has no open tab to record. Open the page you want to record first."
            )
        self._context = contexts[0]
        for page in list(self._context.pages):
            self._attach(page)
        self._context.on("page", lambda page: self._attach(page))
        log(f"CDP recorder attached to {len(self._pages)} tab(s) (session {self.session[:8]})")
        self._ready.set()

    def _pump(self):
        # The sync API only dispatches protocol events (including the __crEmit
        # bindings) while this thread is inside a call that round-trips to the
        # driver. Reading context.pages is served from a local cache and pumps
        # nothing, so use a real request instead.
        with self._lock:
            pages = list(self._pages)
        for page in pages:
            try:
                page.title()
                return
            except Exception:
                continue

    def _submit(self, fn, *args, **kwargs):
        self._cmds.put((fn, args, kwargs))

    def start(self, start_url="", wait=30):
        self._worker.start()
        self._ready.wait(timeout=wait)
        if not self._ready.is_set():
            self._error = self._error or "Timed out attaching to Chrome over CDP."
            self.stop()
            raise RuntimeError(self._error)
        if self._error:
            self.stop()
            raise RuntimeError(self._error)
        self.start_url = start_url or (self._context.pages[0].url if self._context.pages else "")

    def _attach(self, page):
        key = id(page)
        if key in self._attached:
            return
        self._attached.add(key)
        # add_init_script() has no arg parameter in this Playwright version, so
        # the session id is inlined into the source.
        init_script = f"({_RECORDER_JS})({json.dumps(self.session)});"
        try:
            page.expose_binding("__crEmit", self._on_event)
            page.add_init_script(init_script)
            page.evaluate(_RECORDER_JS, self.session)
            with self._lock:
                self._pages.append(page)
            emit("action", f"Recording tab: {page.url[:90]}")
        except Exception as exc:
            self._attached.discard(key)
            log(f"could not attach to tab: {exc}")

    def _on_event(self, source, payload):
        try:
            event = json.loads(payload)
        except (TypeError, ValueError):
            return
        with self._lock:
            self.events.append(event)
        kind = event.get("kind")
        if kind == "click":
            emit("action", f"Click: {event.get('text') or event.get('selector')}")
        elif kind in ("fill", "select"):
            emit("action", f"{kind.title()}: {event.get('text') or event.get('selector')}")
        elif kind == "navigate":
            emit("action", f"Navigate: {event.get('url')}")

    def stop(self):
        # Never browser.close(): we are attached to the user's real Chrome over
        # CDP, and closing would take their window down. Stopping the worker
        # just drops the connection.
        self._done.set()
        if self._worker.is_alive():
            self._worker.join(timeout=10)
        with self._lock:
            return list(self.events)


def _py(value):
    """Render a Python literal for a Playwright locator argument."""
    return repr(value)


_CLICKABLE_TAGS = ("a", "button", "[role='button']", "[role='link']", "[role='tab']", "summary", "label")


def _locator(event):
    """Pick a Playwright locator.

    get_by_text() matches rendered text, which is right for buttons and links
    but wrong for form controls: a text input's "text" is its current value, so
    get_by_text('Salman').fill(...) would target the wrong element entirely.
    Controls therefore always use the CSS path captured at record time.
    """
    text = (event.get("text") or "").strip()
    selector = (event.get("selector") or "").strip()
    kind = event.get("kind")
    if kind == "click" and text and len(text) <= 60:
        target = selector.split(" > ")[-1].strip()
        if any(target.startswith(tag) for tag in _CLICKABLE_TAGS):
            return f"page.get_by_text({_py(text)}).first"
    if selector:
        return f"page.locator({_py(selector)}).first"
    if text:
        return f"page.get_by_text({_py(text)}).first"
    return None


def generate_web_script(name, events, start_url=""):
    """Turn captured CDP events into a Playwright sync-API script."""
    lines = [
        '"""',
        f"Web Recording: {name}",
        f"Recorded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Generated by Creator Platform Recorder (captured from your own Chrome).",
        "",
        "Replays inside the Chrome window that is already open (DevTools port",
        f"{CHROME_DEBUG_PORT}). It never launches a headless or second browser.",
        '"""',
        "",
        "from playwright.sync_api import sync_playwright",
        "",
        f"CDP_URL = 'http://127.0.0.1:{CHROME_DEBUG_PORT}'",
        f"START_URL = {start_url!r}",
        "",
        "",
        "def main():",
        "    with sync_playwright() as p:",
        "        browser = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)",
        "        context = browser.contexts[0] if browser.contexts else browser.new_context()",
        "        pages = [pg for pg in context.pages if pg.url and pg.url != 'about:blank']",
        "        page = pages[0] if pages else context.new_page()",
        "        if START_URL and START_URL not in page.url:",
        "            page.goto(START_URL)",
        "",
    ]
    body = []
    last_url = start_url
    for event in events:
        kind = event.get("kind")
        if kind == "ready":
            continue
        if kind == "navigate":
            url = event.get("url") or ""
            if url and url != last_url:
                body.append(f"        page.goto({_py(url)})")
                last_url = url
            continue
        if kind == "scroll":
            # No element involved, so this must not go through _locator().
            x = int(event.get("x") or 0)
            y = int(event.get("y") or 0)
            body.append(f"        page.evaluate('window.scrollTo({x}, {y})')")
            continue
        locator = _locator(event)
        if not locator:
            continue
        if kind == "click":
            body.append(f"        {locator}.click()")
        elif kind == "fill":
            body.append(f"        {locator}.fill({_py(event.get('value') or '')})")
        elif kind == "select":
            value = event.get("value") or event.get("label") or ""
            body.append(f"        {locator}.select_option({_py(value)})")
        elif kind == "check":
            body.append(f"        {locator}.check()")
        elif kind == "uncheck":
            body.append(f"        {locator}.uncheck()")
        elif kind == "submit":
            body.append(f"        {locator}.click()")

    if not body:
        body.append("        page.wait_for_timeout(500)")

    lines += body
    lines += [
        "        page.wait_for_timeout(500)",
        "        # No browser.close(): the visible Chrome window must stay open.",
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    return "\n".join(lines)


def start_web_recording(url="", relaunch=True):
    global _cdp
    browser_name, error = ensure_debuggable_chrome(relaunch=relaunch, start_url=url)
    if error:
        emit("error", error)
        log(error)
        return
    try:
        import playwright  # noqa: F401
    except ImportError:
        emit("error", "Install playwright: pip install playwright  (no browser download needed)")
        return

    emit("action", f"Attached to {browser_name} — start interacting in that window")
    cdp = ChromeCdp(port=CHROME_DEBUG_PORT)
    try:
        cdp.start(url)
    except Exception as exc:
        emit("error", str(exc))
        log(f"CDP attach failed: {exc}")
        try:
            cdp.stop()
        except Exception:
            pass
        return
    _cdp = cdp


def stop_web_recording():
    global _cdp
    if not _cdp:
        return [], ""
    events = _cdp.stop()
    start_url = _cdp.start_url
    _cdp = None
    return events, start_url


# ══════════════════════════════════════════════════════════════════════════════
# Run a saved script locally — plain run, or under pdb when breakpoints exist
# ══════════════════════════════════════════════════════════════════════════════
def _kill_tree(pid):
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=15)
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def run_script(script, name, debug=False, env_overrides=None):
    global _run_proc, _run_stopped_by_user, _run_stdin

    if not (script or "").strip():
        emit("error", "Run failed: script is empty")
        return
    with _run_lock:
        if _run_proc is not None:
            emit("error", "A script is already running. Stop it first.")
            return
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in (name or "script"))
        path = Path(tempfile.gettempdir()) / f"rec_run_{safe}.py"
        try:
            path.write_text(script, encoding="utf-8")
        except Exception as exc:
            emit("error", f"Run failed: could not write temp file: {exc}")
            return

    child_env = os.environ.copy()
    for key, value in (env_overrides or {}).items():
        if value is None:
            child_env.pop(key, None)
        else:
            child_env[key] = str(value)

    # Debug mode runs under pdb so breakpoint() calls actually pause, and keeps
    # stdin open so Step/Continue can be fed in from the web UI.
    command = [sys.executable, "-m", "pdb", str(path)] if debug else [sys.executable, str(path)]

    def worker():
        global _run_proc, _run_stopped_by_user, _run_stdin
        _run_stopped_by_user = False
        _run_stdin = None
        emit("run_started", f"Running {name} ..." + (" (debug mode)" if debug else ""))
        try:
            _run_proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if debug else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(path.parent),
                env=child_env,
            )
            if debug:
                _run_stdin = _run_proc.stdin
            for line in _run_proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                emit("run_output", line)
                # `python -m pdb` restarts the script when it ends rather than
                # exiting, which would leave the run "running" forever and
                # block every later run. Quit it once the program is done.
                if debug and "The program finished" in line:
                    try:
                        _run_stdin.write("quit\n")
                        _run_stdin.flush()
                    except Exception:
                        pass
            code = _run_proc.wait()
            if _run_stopped_by_user:
                emit("run_error", f"{name} stopped by user")
            elif code == 0:
                emit("run_finished", f"{name} finished successfully")
            else:
                emit("run_error", f"{name} exited with code {code}")
        except Exception as exc:
            emit("run_error", f"Run failed: {exc}")
        finally:
            _run_proc = None
            _run_stdin = None

    threading.Thread(target=worker, daemon=True).start()


def stop_run():
    global _run_stopped_by_user
    with _run_lock:
        proc = _run_proc
    if proc is None:
        emit("error", "Nothing is running")
        return
    _run_stopped_by_user = True
    try:
        _kill_tree(proc.pid)
    except Exception as exc:
        log(f"error stopping run: {exc}")


def send_debug_input(command_text):
    """Write a pdb command ('n' step, 'c' continue) into the paused child."""
    proc_stdin = _run_stdin
    if proc_stdin is None:
        emit("error", "Nothing is paused. Start a run with breakpoints first.")
        return
    try:
        proc_stdin.write(f"{command_text}\n")
        proc_stdin.flush()
        emit("debug_paused", f"Sent '{command_text}'")
    except Exception as exc:
        emit("error", f"Could not send '{command_text}': {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Socket.IO protocol
# ══════════════════════════════════════════════════════════════════════════════
AGENT_TOKEN = ""


@_sio.event
def connect():
    log("Connected to Creator Platform")
    _sio.emit("recorder_register", {
        "version": AGENT_VERSION,
        "platform": sys.platform,
        "hostname": os.environ.get("COMPUTERNAME", "unknown"),
        "token": AGENT_TOKEN,
    })


@_sio.event
def disconnect():
    log("Disconnected from Creator Platform")


@_sio.on("recorder_command")
def on_command(data):
    global _recording, _record_type, _record_name
    data = data or {}
    command = data.get("cmd")
    record_type = data.get("type", "desktop")
    url = data.get("url", "")
    app_path = data.get("app_path", "")
    name = (data.get("name") or "").strip() or fmt_name()
    log(f"Command: {command} type={record_type}")

    if command == "start":
        if _recording:
            emit("error", "Already recording")
            return
        _recording = True
        _record_type = record_type
        _record_name = name
        if record_type == "web":
            start_web_recording(url, relaunch=ALLOW_RELAUNCH)
        else:
            start_desktop_recording(app_path)
        emit("started", f"Recording started ({record_type}) - do it in the agent window",
             record_type=record_type, name=name)

    elif command == "stop":
        if not _recording:
            emit("error", "Not recording")
            return
        _recording = False
        name = _record_name or name
        try:
            if _record_type == "web":
                events, start_url = stop_web_recording()
                time.sleep(0.5)
                script = generate_web_script(name, events, start_url)
                count = len(events)
            else:
                stop_desktop_recording()
                script = generate_desktop_script(name)
                count = len(_events)
            if not script.strip() or count == 0:
                emit("error", "No interactions were captured — nothing saved.")
                return
            _sio.emit("recorder_save", {
                "name": name,
                "record_type": _record_type,
                "script": script,
                "event_count": count,
            })
            log(f"Script sent to hub ({len(script)} chars, {count} events)")
        except Exception as exc:
            log(f"Error while stopping recording: {exc}")
            emit("error", f"Stop failed: {exc}")

    elif command == "run":
        run_script(
            data.get("script", ""),
            data.get("name", "script"),
            debug=bool(data.get("debug", False)),
            env_overrides=data.get("env") or {},
        )

    elif command == "stop_run":
        stop_run()

    elif command == "debug_input":
        send_debug_input((data.get("input") or "n").strip() or "n")

    elif command == "ping":
        emit("action", "Agent alive")


# ══════════════════════════════════════════════════════════════════════════════
# Entry points
# ══════════════════════════════════════════════════════════════════════════════
ALLOW_RELAUNCH = True


def main_cli(args):
    global AGENT_TOKEN, ALLOW_RELAUNCH
    AGENT_TOKEN = args.token
    ALLOW_RELAUNCH = not args.no_relaunch_chrome
    log(f"Recorder Agent v{AGENT_VERSION}")
    log(f"Connecting to {args.hub}")
    while True:
        try:
            _sio.connect(args.hub, transports=["websocket", "polling"],
                         auth={"token": args.token} if args.token else None)
            _sio.wait()
        except Exception as exc:
            log(f"Connection failed: {exc} — retrying in 5s...")
            time.sleep(5)


def launch_gui(prefill_hub=DEFAULT_HUB, prefill_token="", autoconnect=False):
    global AGENT_TOKEN, ALLOW_RELAUNCH
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print("tkinter unavailable — run with --cli instead")
        return

    root = tk.Tk()
    root.title("Creator Platform — Recorder Agent")
    root.geometry("430x250")
    root.resizable(False, False)
    root.configure(bg="#1e2130")

    tk.Label(root, text="Creator Platform", font=("Segoe UI", 14, "bold"),
             bg="#1e2130", fg="#ffffff").pack(pady=(20, 2))
    tk.Label(root, text="Recorder Agent", font=("Segoe UI", 10),
             bg="#1e2130", fg="#888888").pack(pady=(0, 14))

    frame = tk.Frame(root, bg="#1e2130")
    frame.pack(padx=20, fill="x")
    tk.Label(frame, text="Hub URL:", bg="#1e2130", fg="#aaaaaa",
             font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=4)
    url_var = tk.StringVar(value=prefill_hub)
    tk.Entry(frame, textvariable=url_var, width=32, bg="#2a2d3a", fg="white",
             insertbackground="white", font=("Segoe UI", 10), relief="flat", bd=4
             ).grid(row=0, column=1, padx=(8, 0), pady=4)
    tk.Label(frame, text="Token:", bg="#1e2130", fg="#aaaaaa",
             font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=4)
    token_var = tk.StringVar(value=prefill_token)
    tk.Entry(frame, textvariable=token_var, width=32, bg="#2a2d3a", fg="white",
             insertbackground="white", font=("Segoe UI", 10), relief="flat", bd=4
             ).grid(row=1, column=1, padx=(8, 0), pady=4)

    status_var = tk.StringVar(value="● Disconnected")
    status_lbl = tk.Label(root, textvariable=status_var, font=("Segoe UI", 10),
                          bg="#1e2130", fg="#f87171")
    status_lbl.pack(pady=8)

    state = {"connected": False, "thread": None}

    def do_connect():
        hub = url_var.get().strip()
        if not hub:
            messagebox.showerror("Error", "Enter the Hub URL")
            return
        global AGENT_TOKEN
        AGENT_TOKEN = token_var.get().strip()
        btn_connect.config(state="disabled", text="Connecting...")
        status_var.set("● Connecting...")
        status_lbl.config(fg="#f0a500")

        def loop():
            while state["connected"]:
                try:
                    if not _sio.connected:
                        _sio.connect(hub, transports=["websocket", "polling"],
                                     auth={"token": AGENT_TOKEN} if AGENT_TOKEN else None)
                    root.after(0, lambda: (
                        status_var.set("● Connected"),
                        status_lbl.config(fg="#4ade80"),
                        btn_connect.config(state="disabled", text="Connected"),
                        btn_disconnect.config(state="normal"),
                    ))
                    _sio.wait()
                except Exception:
                    if not state["connected"]:
                        break
                    root.after(0, lambda: (status_var.set("● Reconnecting..."), status_lbl.config(fg="#f0a500")))
                    time.sleep(5)

        state["thread"] = threading.Thread(target=loop, daemon=True)
        state["thread"].start()

    def do_disconnect():
        state["connected"] = False
        try:
            _sio.disconnect()
        except Exception:
            pass
        status_var.set("● Disconnected")
        status_lbl.config(fg="#f87171")
        btn_connect.config(state="normal", text="Connect")
        btn_disconnect.config(state="disabled")

    buttons = tk.Frame(root, bg="#1e2130")
    buttons.pack(pady=4)
    btn_connect = tk.Button(buttons, text="Connect", command=do_connect, bg="#4ade80",
                            fg="#000000", font=("Segoe UI", 10, "bold"), width=12,
                            relief="flat", cursor="hand2")
    btn_connect.grid(row=0, column=0, padx=6)
    btn_disconnect = tk.Button(buttons, text="Disconnect", command=do_disconnect, bg="#f87171",
                               fg="#000000", font=("Segoe UI", 10), width=12,
                               relief="flat", cursor="hand2", state="disabled")
    btn_disconnect.grid(row=0, column=1, padx=6)

    state["connected"] = False
    if autoconnect:
        # Launched by Start_Recorder_Agent.bat, which passes --hub: connect
        # straight away instead of making the user press Connect.
        root.after(150, do_connect)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Creator Platform Recorder Agent")
    parser.add_argument("--hub", default=DEFAULT_HUB, help="Creator Platform base URL")
    parser.add_argument("--token", default=os.environ.get("RECORDER_AGENT_TOKEN", ""),
                        help="Agent token (must match RECORDER_AGENT_TOKEN on the server)")
    parser.add_argument("--cli", action="store_true", help="Run without the tkinter window")
    parser.add_argument("--no-relaunch-chrome", action="store_true",
                        help="Fail instead of launching Chrome if the debug port is closed")
    args = parser.parse_args()
    global ALLOW_RELAUNCH
    ALLOW_RELAUNCH = not args.no_relaunch_chrome
    if args.cli:
        main_cli(args)
    else:
        launch_gui(args.hub, args.token, autoconnect="--hub" in sys.argv)


if __name__ == "__main__":
    main()
