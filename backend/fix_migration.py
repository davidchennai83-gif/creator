import subprocess
result = subprocess.run([r'.\.venv\Scripts\python.exe', '-m', 'alembic', 'head'], capture_output=True, text=True, cwd=r'G:\my_tool\creator-platform\backend')
print('stdout:', result.stdout)
print('stderr:', result.stderr)
print('returncode:', result.returncode)