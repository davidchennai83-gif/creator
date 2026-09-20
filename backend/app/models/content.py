from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON, Enum
from datetime import datetime
from sqlalchemy import Uuid as UUID, Enum as ENUM
import enum

class ContentStatus(enum.Enum):
    IDEA = "IDEA"
    DRAFT = "DRAFT"
    SCRIPT_READY = "SCRIPT_READY"
    MEDIA_READY = "MEDIA_READY"
    VIDEO_PROCESSING = "VIDEO_PROCESSING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"

class ContentCategory(enum.Enum):
    TUTORIAL = "TUTORIAL"
    VLOG = "VLOG"
    REVIEW = "REVIEW"
    EDUCATION = "EDUCATION"
    ENTERTAINMENT = "ENTERTAINMENT"
    PROMOTION = "PROMOTION"
    NEWS = "NEWS"
    OTHER = "OTHER"

class Content(Base, UUIDMixin):
    __tablename__ = "content"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(ENUM(ContentCategory), nullable=True)
    status = Column(ENUM(ContentStatus), default=ContentStatus.IDEA, nullable=False, index=True)
    language = Column(String(10), nullable=True)
    tags = Column(JSON, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, default=0)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    published_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)

class ContentScript(Base, UUIDMixin):
    __tablename__ = "content_scripts"

    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True)
    script_text = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    cta = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)
    language = Column(String(10), nullable=True)
    version = Column(Integer, default=1)

class ContentAsset(Base, UUIDMixin):
    __tablename__ = "content_assets"

    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(50), nullable=False)
    file_path = Column(String(1000), nullable=True)
    file_url = Column(String(1000), nullable=True)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), nullable=True)
    meta_data = Column(JSON, nullable=True)
