"""List tables in the local SQLite database (diagnostic helper)."""
import sqlite3
from pathlib import Path

conn = sqlite3.connect(Path(__file__).with_name('creator_platform.db'))
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', [t[0] for t in tables])
conn.close()
