from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON, Enum
from datetime import datetime
from app.utils.time import utcnow
from sqlalchemy import Uuid as UUID, Enum as ENUM
import enum

class SocialPlatform(Base, UUIDMixin):
    __tablename__ = "social_platforms"

    name = Column(String(100), nullable=False, unique=True)
    api_base_url = Column(String(500), nullable=True)
    oauth_url = Column(String(500), nullable=True)
    scopes = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)

class SocialAccount(Base, UUIDMixin):
    __tablename__ = "social_accounts"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    platform_id = Column(UUID(as_uuid=True), ForeignKey("social_platforms.id"), nullable=False, index=True)
    account_name = Column(String(255), nullable=True)
    account_id = Column(String(255), nullable=False)
    access_token_encrypted = Column(String(500), nullable=True)
    refresh_token_encrypted = Column(String(500), nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    is_connected = Column(Boolean, default=False)
    last_sync = Column(DateTime, nullable=True)
    last_successful_post = Column(DateTime, nullable=True)

class SocialPost(Base, UUIDMixin):
    __tablename__ = "social_posts"

    publishing_job_id = Column(UUID(as_uuid=True), ForeignKey("publishing_jobs.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("social_accounts.id"), nullable=False)
    post_id = Column(String(255), nullable=True)
    caption = Column(Text, nullable=True)
    media_url = Column(String(1000), nullable=True)
    status = Column(String(20), default="PENDING")
    published_at = Column(DateTime, nullable=True)

class SocialAnalytics(Base, UUIDMixin):
    __tablename__ = "social_analytics"

    post_id = Column(UUID(as_uuid=True), ForeignKey("social_posts.id"), nullable=True, index=True)
    platform = Column(String(50), nullable=False)
    views = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    collected_at = Column(DateTime, nullable=False, default=utcnow)
