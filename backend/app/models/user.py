from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, DateTime
from datetime import datetime
from sqlalchemy import Uuid as UUID, Enum as ENUM, ForeignKey
import enum

class UserRole(enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"

class UserStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

class User(Base, UUIDMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(ENUM(UserRole), default=UserRole.VIEWER, nullable=False)

class RefreshToken(Base, UUIDMixin):
    __tablename__ = "refresh_tokens"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

class Session(Base, UUIDMixin):
    __tablename__ = "sessions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_token_hash = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
