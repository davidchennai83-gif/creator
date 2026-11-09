"""Post-reboot health check for the creator platform (ASCII output only).

Run after signing in to Windows:

    python scripts/boot_check.py

It checks the things that must come back automatically: backend, OpenCode
server, the recorder Chrome (CDP 9222), Ollama, Tailscale funnel and free disk
space. Exit code 0 = all good, 1 = something needs attention.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAILSCALE = Path(r"C:\Program Files\Tailscale\tailscale.exe")

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def http_json(url: str, timeout: float = 5.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read())
    except Exception:
        return None


def run(cmd: list[str], timeout: float = 10.0) -> str:
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=flags, errors="replace",
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def check_backend() -> None:
    health = http_json("http://127.0.0.1:8000/health")
    ok = bool(health and health.get("server") == "hypercorn")
    record("Backend  :8000", ok, "hypercorn healthy" if ok else "no /health response")


def check_frontend() -> None:
    index = ROOT / "frontend" / "dist" / "index.html"
    if not index.is_file():
        record("Frontend build", False, "frontend/dist/index.html missing")
        return
    text = index.read_text(encoding="utf-8", errors="replace")
    bundle = "assets/index-" in text
    record("Frontend build", bundle, "dist bundle present" if bundle else "index.html has no bundle")


def check_opencode() -> None:
    if not port_open(4096):
        record("OpenCode :4096", False, "not listening (starts on first chat)")
        return
    info = http_json("http://127.0.0.1:4096/api/info")
    record("OpenCode :4096", True, "listening" if info is None else "API answers (401 without auth is normal)")


def check_chrome() -> None:
    if not port_open(9222):
        record("Recorder Chrome :9222", False, "not listening (upload automation needs it)")
        return
    version = http_json("http://127.0.0.1:9222/json/version")
    record(
        "Recorder Chrome :9222", True,
        f"CDP ready ({version.get('Browser', 'unknown')})" if version else "CDP port open",
    )


def check_ollama() -> None:
    if not port_open(11434):
        record("Ollama :11434", False, "not listening (history renders need it)")
        return
    tags = http_json("http://127.0.0.1:11434/api/tags")
    count = len((tags or {}).get("models", []))
    record("Ollama :11434", True, f"listening, {count} model(s)")


def check_tailscale() -> None:
    if not TAILSCALE.is_file():
        record("Tailscale", False, "tailscale.exe not found")
        return
    status = run([str(TAILSCALE), "status", "--json"])
    online = False
    dns = ""
    try:
        payload = json.loads(status)
        me = payload.get("Self") or {}
        online = bool(me.get("Online"))
        dns = str(me.get("DNSName") or "").rstrip(".")
    except Exception:
        pass
    record("Tailscale online", online, dns or "no status")

    funnel = run([str(TAILSCALE), "funnel", "status"])
    on = "Funnel on" in funnel and "127.0.0.1:8000" in funnel
    record("Funnel -> 8000", on, "https URL serves the app" if on else "funnel is off")


def check_disk() -> None:
    for label, path in (("Disk C:", "C:\\"), ("Disk D:", str(ROOT.drive) + "\\" if ROOT.drive else "D:\\")):
        try:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024 ** 3)
            record(label, free_gb >= 5, f"{free_gb:.1f} GB free")
        except Exception as exc:  # noqa: BLE001
            record(label, False, str(exc))


def check_schedule() -> None:
    script = ROOT / "scripts" / "today_status.py"
    if not script.is_file():
        record("Schedule data", False, "scripts/today_status.py missing")
        return
    output = run([sys.executable, str(script), "--short"], timeout=20)
    lines = [line for line in output.splitlines() if line.strip()]
    ok = any(line.startswith("TODAY") for line in lines)
    detail = " | ".join(lines[1:4]) if ok else output.strip()[:160]
    record("Schedule data", ok, detail)


def main() -> int:
    print(f"BOOT CHECK  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project: {ROOT}")
    print()
    for check in (
        check_backend, check_frontend, check_opencode, check_chrome,
        check_ollama, check_tailscale, check_disk, check_schedule,
    ):
        try:
            check()
        except Exception as exc:  # noqa: BLE001
            record(check.__name__, False, f"check crashed: {exc}")

    failed = 0
    for name, ok, detail in results:
        if not ok:
            failed += 1
        print(f"[{'OK  ' if ok else 'FAIL'}] {name:<24} {detail}")

    print()
    if failed:
        print(f"RESULT: {failed} check(s) failed.")
        print("Next: wait up to 10 minutes for the watchdog, then run this again.")
        print("Logs: backend/storage/web-server.log, watchdog.log")
        return 1
    print("RESULT: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
