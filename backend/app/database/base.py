from sqlalchemy import Column, DateTime, String
from sqlalchemy import Uuid as UUID, MetaData
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from app.utils.time import utcnow
import uuid

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={"ix": "ix_%(table_name)s_%(column_0_name)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"})
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

class UUIDMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
