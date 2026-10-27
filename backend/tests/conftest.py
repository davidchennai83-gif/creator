import os
import tempfile
from pathlib import Path
import pytest

# Always use a disposable database, never the user's configured database.
temporary = tempfile.TemporaryDirectory(prefix="creator-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(temporary.name) / 'test.db').as_posix()}"
os.environ["STORAGE_PATH"] = str(Path(temporary.name) / 'storage')
# Automation projects and recordings must never touch the developer's real storage.
os.environ["AUTOMATION_PATH"] = str(Path(temporary.name) / 'automation')
os.environ["RECORDINGS_PATH"] = str(Path(temporary.name) / 'recorder')
os.environ["JWT_SECRET"] = "test-access-signing-key-" + "a" * 32
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-signing-key-" + "b" * 32
os.environ["ENVIRONMENT"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["ALLOW_REGISTRATION"] = "true"
os.environ["REQUIRE_REDIS"] = "false"
os.environ["BACKGROUND_WORKERS"] = "false"

from fastapi.testclient import TestClient
from app.main import create_app
from app.database.engine import sync_engine, init_db
from app.models import Base

@pytest.fixture(scope="session", autouse=True)
def schema():
    init_db()
    yield
    sync_engine.dispose()
    temporary.cleanup()

@pytest.fixture
def client():
    with sync_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        yield client

@pytest.fixture
def account(client):
    response = client.post('/api/v1/auth/register', json={"email":"creator@example.com", "username":"creator", "password":"A secure password 123"})
    assert response.status_code == 201, response.text
    return response.json()['data']

@pytest.fixture
def headers(account):
    return {"Authorization": f"Bearer {account['access_token']}"}
