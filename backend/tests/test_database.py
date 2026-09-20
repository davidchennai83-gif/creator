import pytest
from sqlalchemy import inspect, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from uuid import uuid4
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.database.engine import sync_engine, Base as EngineBase
from app.models import Base, Content

def test_migration_matches_models():
    assert EngineBase is Base
    with sync_engine.connect() as db:
        assert set(Base.metadata.tables).issubset(inspect(db).get_table_names())
        assert compare_metadata(MigrationContext.configure(db),Base.metadata)==[]

def test_foreign_keys_enforced():
    with pytest.raises(IntegrityError):
        with sync_engine.begin() as db:
            db.execute(insert(Content).values(id=uuid4(),user_id=uuid4(),title='orphan'))

def test_postgres_ddl_compiles():
    for table in Base.metadata.sorted_tables:
        assert 'CREATE TABLE' in str(CreateTable(table).compile(dialect=postgresql.dialect()))
