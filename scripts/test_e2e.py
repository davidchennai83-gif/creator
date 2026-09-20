"""Run browser tests against an isolated, real Hypercorn process."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix='creator-e2e-') as folder:
        env = os.environ.copy()
        env.update(DATABASE_URL=f"sqlite+aiosqlite:///{(Path(folder)/'test.db').as_posix()}", JWT_SECRET='e2e-access-'+'a'*40, JWT_REFRESH_SECRET='e2e-refresh-'+'b'*40, ENVIRONMENT='development', COOKIE_SECURE='false', REQUIRE_REDIS='false', ALLOW_REGISTRATION='true', SERVER_HOST='127.0.0.1')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        env['SERVER_PORT']=str(port)
        env['E2E_BASE_URL']=f'http://127.0.0.1:{port}'
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT/'backend',env=env,check=True)
        with (Path(folder)/'server.log').open('w+',encoding='utf-8') as log:
            server=subprocess.Popen([sys.executable,str(ROOT/'backend'/'start.py')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(60):
                    if server.poll() is not None:
                        raise RuntimeError('Hypercorn exited before startup')
                    try:
                        with urllib.request.urlopen(env['E2E_BASE_URL']+'/ready',timeout=1) as response:
                            if response.status==200:
                                break
                    except OSError:
                        time.sleep(0.5)
                else:
                    raise RuntimeError('Hypercorn readiness timed out')
                result=subprocess.run([shutil.which('node') or 'node',str(ROOT/'frontend/node_modules/@playwright/test/cli.js'),'test'],cwd=ROOT/'frontend',env=env)
                if result.returncode:
                    raise RuntimeError('Browser workflow failed')
            except Exception:
                log.seek(0)
                print(log.read())
                raise
            finally:
                server.terminate()
                server.wait(timeout=15)

if __name__=='__main__':
    main()
