from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey, JSON, Enum
from datetime import datetime
from sqlalchemy import Uuid as UUID, Enum as ENUM
import enum

class VideoStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class VideoJobStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

class Video(Base, UUIDMixin):
    __tablename__ = "videos"

    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id"), nullable=False, index=True)
    input_paths = Column(JSON, nullable=True)
    intermediate_paths = Column(JSON, nullable=True)
    final_path = Column(String(1000), nullable=True)
    thumbnail_path = Column(String(1000), nullable=True)
    subtitle_path = Column(String(1000), nullable=True)
    duration = Column(Integer, default=0)
    resolution = Column(String(20), nullable=True)
    status = Column(ENUM(VideoStatus), default=VideoStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class VideoJob(Base, UUIDMixin):
    __tablename__ = "video_jobs"

    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    job_type = Column(String(50), nullable=False)
    status = Column(ENUM(VideoJobStatus), default=VideoJobStatus.PENDING, nullable=False)
    progress_percent = Column(Integer, default=0)
    worker_id = Column(String(100), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

class ScheduledTask(Base, UUIDMixin):
    __tablename__ = "scheduled_tasks"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(500), nullable=False)
    content_ref = Column(String(200), nullable=True)
    platform = Column(String(50), nullable=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id"), nullable=True)
    cron_expression = Column(String(100), nullable=True)
    schedule_date = Column(DateTime, nullable=True)
    schedule_time = Column(String(10), nullable=True)
    timezone = Column(String(50), default="UTC")
    retry_count = Column(Integer, default=0)
    priority = Column(String(20), default="MEDIUM")
    status = Column(String(20), default="PENDING", index=True)
    executed_at = Column(DateTime, nullable=True)

class PublishingJob(Base, UUIDMixin):
    __tablename__ = "publishing_jobs"

    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_tasks.id"), nullable=True)
    platform = Column(String(50), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id"), nullable=False)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    status = Column(String(20), default="PENDING", index=True)
    error_message = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
