"""Create local secrets once and migrate without deleting existing data."""
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    env = ROOT / '.env'
    if not env.exists():
        with env.open('x', encoding='utf-8') as stream:
            stream.write(f'JWT_SECRET={secrets.token_urlsafe(48)}\nJWT_REFRESH_SECRET={secrets.token_urlsafe(48)}\nDB_PASSWORD={secrets.token_urlsafe(32)}\n')
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.database.engine import init_db
    init_db()
    print('Database migrated. Existing .env and database records were preserved.')

if __name__ == '__main__':
    main()
