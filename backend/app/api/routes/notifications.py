from datetime import datetime
from app.utils.time import utcnow
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from app.database.engine import get_db
from app.models.system import Notification
from app.api.deps import get_current_user
from app.schemas.common import success

router = APIRouter()

@router.get("")
async def list_notifications(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(get_current_user), db=Depends(get_db)):
    items = (await db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc(), Notification.id).offset((page-1)*limit).limit(limit))).all()
    return success({"items": [{"id": str(i.id), "title": i.title, "message": i.message, "is_read": i.is_read} for i in items], "page": page})

@router.put("/{notification_id}/read")
async def mark_read(notification_id: UUID, user=Depends(get_current_user), db=Depends(get_db)):
    item = await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not item:
        raise HTTPException(404, "Notification not found")
    item.is_read, item.read_at = True, utcnow()
    await db.commit()
    return success(message="Marked as read")
