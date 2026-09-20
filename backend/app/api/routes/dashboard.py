from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.database.engine import get_db
from app.models.user import User
from app.models.content import Content, ContentStatus
from app.schemas.common import success

router = APIRouter()


@router.get("")
async def dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Content.status, func.count()).where(Content.user_id == user.id).group_by(Content.status))).all()
    counts = {status.value: count for status, count in rows}
    return success({"content_by_status": counts, "total_content": sum(counts.values()), "drafts": counts.get("DRAFT", 0), "integrations_available": False})
