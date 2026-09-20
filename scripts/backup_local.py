"""SQLite online backup; pause content/media writes for a consistent combined snapshot."""
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

def main():
    from app.config.settings import settings, get_sync_database_url
    from sqlalchemy.engine import make_url
    url = make_url(get_sync_database_url())
    if url.get_backend_name() != 'sqlite':
        raise SystemExit('Use backup.sh for PostgreSQL.')
    source = Path(url.database).resolve()
    if not source.is_file():
        raise SystemExit('Database not found. Run setup first.')
    destination = ROOT / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True) as db, sqlite3.connect(destination / 'creator_platform.db') as backup:
        db.backup(backup)
    media = Path(settings.STORAGE_PATH)
    if media.exists():
        shutil.copytree(media, destination / 'storage')
    print(f'Backup completed: {destination}')

if __name__ == '__main__':
    main()
