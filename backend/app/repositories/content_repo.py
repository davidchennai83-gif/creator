from fastapi import HTTPException
from sqlalchemy import select, func
from app.models.content import Content


async def owned(db, content_id, user_id):
    item = await db.scalar(select(Content).where(Content.id == content_id, Content.user_id == user_id))
    if item is None:
        raise HTTPException(404, "Content not found")
    return item


async def list_owned(db, user_id, page, limit, search):
    filters = [Content.user_id == user_id, Content.archived_at.is_(None)]
    if search:
        filters.append(Content.title.icontains(search, autoescape=True))
    total = await db.scalar(select(func.count()).select_from(Content).where(*filters))
    items = (await db.scalars(select(Content).where(*filters).order_by(Content.created_at.desc(), Content.id).offset((page - 1) * limit).limit(limit))).all()
    return items, total
