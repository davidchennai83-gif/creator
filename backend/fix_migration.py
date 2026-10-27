"""Print the current Alembic head revision (diagnostic helper)."""
import subprocess
import sys
from pathlib import Path

result = subprocess.run([sys.executable, '-m', 'alembic', 'head'], capture_output=True, text=True,
                        cwd=str(Path(__file__).parent))
print('stdout:', result.stdout)
print('stderr:', result.stderr)
print('returncode:', result.returncode)
