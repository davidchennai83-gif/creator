"""Quiet per-user launcher. Keep the single-URL web server alive without a CMD window."""
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))


def main():
    from app.config.settings import settings
    storage = Path(settings.STORAGE_PATH)
    storage.mkdir(parents=True, exist_ok=True)
    # Multiple launcher clicks or logon triggers must not create competing workers.
    with (storage / 'web-launcher.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        url = f'http://127.0.0.1:{settings.SERVER_PORT}/health'
        python = BASE / '.venv' / 'Scripts' / 'python.exe'
        while True:
            try:
                with urlopen(url, timeout=5) as response:
                    healthy = json.load(response).get('server') == 'hypercorn'
                if healthy:
                    time.sleep(15)
                    continue
            except Exception:
                pass
            log = storage / 'web-server.log'
            if log.exists() and log.stat().st_size > 10 * 1024 * 1024:
                log.replace(storage / 'web-server.previous.log')
            with log.open('ab', buffering=0) as output:
                child = subprocess.Popen([str(python), str(BASE / 'start.py')], cwd=BASE,
                                         stdout=output, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                child.wait()
            time.sleep(10)


if __name__ == '__main__':
    main()
