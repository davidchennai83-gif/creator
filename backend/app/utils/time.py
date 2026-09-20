from datetime import datetime, timezone

def utcnow():
    """Persist UTC-naive values consistently on SQLite and PostgreSQL; emit API timestamps with Z."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
