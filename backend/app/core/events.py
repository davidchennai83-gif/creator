from dataclasses import dataclass, field
from datetime import datetime
from app.utils.time import utcnow
from typing import Any, Optional
from enum import Enum

class EventType(str, Enum):
    USER_LOGIN = "USER_LOGIN"
    USER_REGISTER = "USER_REGISTER"
    USER_LOGOUT = "USER_LOGOUT"
    VIDEO_CREATED = "VIDEO_CREATED"
    VIDEO_UPDATED = "VIDEO_UPDATED"
    VIDEO_GENERATED = "VIDEO_GENERATED"
    VIDEO_APPROVED = "VIDEO_APPROVED"
    VIDEO_REJECTED = "VIDEO_REJECTED"
    VIDEO_PUBLISHED = "VIDEO_PUBLISHED"
    VIDEO_FAILED = "VIDEO_FAILED"
    POST_SCHEDULED = "POST_SCHEDULED"
    POST_PUBLISHED = "POST_PUBLISHED"
    POST_FAILED = "POST_FAILED"
    SOCIAL_ACCOUNT_CONNECTED = "SOCIAL_ACCOUNT_CONNECTED"
    AFFILIATE_ADDED = "AFFILIATE_ADDED"
    PRODUCT_CREATED = "PRODUCT_CREATED"
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    NOTIFICATION_SENT = "NOTIFICATION_SENT"
    TASK_EXECUTED = "TASK_EXECUTED"
    TASK_FAILED = "TASK_FAILED"

@dataclass
class DomainEvent:
    event_type: EventType
    user_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)
    ip_address: Optional[str] = None
    result: str = "success"

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "result": self.result
        }
