from datetime import datetime
from app.utils.time import utcnow
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, editor, unavailable
from app.database.engine import get_db
from app.models.content import Content, ContentStatus
from app.models.system import AuditLog
from app.models.user import User
from app.repositories import content_repo
from app.schemas.common import success
from app.schemas.content import ContentInput

router = APIRouter()


def serialize(item):
    return {"id": str(item.id), "title": item.title, "description": item.description, "category": item.category.value if item.category else None, "status": item.status.value, "language": item.language, "tags": item.tags or [], "created_at": item.created_at.isoformat() + "Z"}


@router.get("")
async def list_content(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), search: str = Query("", max_length=200), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items, total = await content_repo.list_owned(db, user.id, page, limit, search)
    return success({"items": [serialize(i) for i in items], "total": total, "page": page, "limit": limit})


@router.post("", status_code=201)
async def create(data: ContentInput, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    item = Content(user_id=user.id, status=ContentStatus.DRAFT, **data.model_dump())
    db.add(item)
    await db.flush()
    db.add(AuditLog(user_id=user.id, action="CONTENT_CREATED", entity_id=str(item.id), entity_type="content"))
    await db.commit()
    return success(serialize(item), "Draft saved")


@router.get("/{content_id}")
async def get_content(content_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return success(serialize(await content_repo.owned(db, content_id, user.id)))


@router.put("/{content_id}")
async def update(content_id: UUID, data: ContentInput, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    item = await content_repo.owned(db, content_id, user.id)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.add(AuditLog(user_id=user.id, action="CONTENT_UPDATED", entity_id=str(item.id), entity_type="content"))
    await db.commit()
    return success(serialize(item))


@router.delete("/{content_id}")
async def archive(content_id: UUID, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    item = await content_repo.owned(db, content_id, user.id)
    item.status = ContentStatus.ARCHIVED
    item.archived_at = utcnow()
    db.add(AuditLog(user_id=user.id, action="CONTENT_ARCHIVED", entity_id=str(item.id), entity_type="content"))
    await db.commit()
    return success(message="Archived")


@router.post("/{content_id}/{action}")
async def pending_action(content_id: UUID, action: str, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await content_repo.owned(db, content_id, user.id)
    unavailable()
