from collections.abc import AsyncIterator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.config.settings import settings, get_sync_database_url
from app.database.base import Base

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
options = {"poolclass": NullPool} if is_sqlite else {"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True}
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, **options)
sync_engine = create_engine(get_sync_database_url(), echo=settings.DEBUG, **options)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

if is_sqlite:
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    event.listen(engine.sync_engine, "connect", configure_sqlite)
    event.listen(sync_engine, "connect", configure_sqlite)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def init_db():
    """Explicit migration command, not an implicit create_all on API startup."""
    from alembic import command
    from alembic.config import Config
    from app.config.settings import BACKEND_DIR
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
