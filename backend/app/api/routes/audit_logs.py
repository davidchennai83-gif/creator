from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from app.database.engine import get_db
from app.models.system import AuditLog
from app.api.deps import get_current_user
from app.schemas.common import success

router = APIRouter()

@router.get("")
async def list_logs(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(get_current_user), db=Depends(get_db)):
    items = (await db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.timestamp.desc(), AuditLog.id).offset((page-1)*limit).limit(limit))).all()
    return success({"items": [{"id": str(i.id), "action": i.action, "result": i.result, "timestamp": i.timestamp.isoformat() + "Z"} for i in items], "page": page})
