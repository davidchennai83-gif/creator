from app.database.base import Base, UUIDMixin
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, JSON, Enum
from datetime import datetime
from app.utils.time import utcnow
from sqlalchemy import Uuid as UUID, Enum as ENUM, Numeric
import enum

class NotificationType(enum.Enum):
    VIDEO_READY = "VIDEO_READY"
    VIDEO_GENERATION_FAILED = "VIDEO_GENERATION_FAILED"
    POST_PUBLISHED = "POST_PUBLISHED"
    POST_FAILED = "POST_FAILED"
    SCHEDULED_TASK_UPCOMING = "SCHEDULED_TASK_UPCOMING"
    AFFILIATE_ORDER = "AFFILIATE_ORDER"
    PRODUCT_ORDER = "PRODUCT_ORDER"
    LOW_STOCK = "LOW_STOCK"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    SYSTEM_ERROR = "SYSTEM_ERROR"

class NotificationChannel(enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    PUSH = "PUSH"

class Notification(Base, UUIDMixin):
    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(ENUM(NotificationType), nullable=False)
    title = Column(String(500), nullable=True)
    message = Column(Text, nullable=True)
    channel = Column(ENUM(NotificationChannel), default=NotificationChannel.IN_APP)
    meta_data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_logs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    result = Column(String(20), default="success")
    meta_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow)

class AIRequest(Base, UUIDMixin):
    __tablename__ = "ai_requests"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=True)
    prompt = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost = Column(Numeric(18, 6), default=0)
    status = Column(String(20), default="COMPLETED")

class AIUsage(Base, UUIDMixin):
    __tablename__ = "ai_usage"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Numeric(18, 6), default=0)
    by_provider = Column(JSON, nullable=True)

class SystemSetting(Base, UUIDMixin):
    __tablename__ = "system_settings"

    setting_key = Column(String(200), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=True)
    updated_by = Column(String(255), nullable=True)
    updated_at = Column(DateTime, nullable=True)
