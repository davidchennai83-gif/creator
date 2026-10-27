import asyncio
import hashlib
from datetime import datetime, timedelta
from app.utils.time import utcnow
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from app.config.settings import settings
from app.core.security import hash_password, verify_password, create_token_pair, decode_refresh_token
from app.models.user import User, UserRole, Session
from app.models.system import AuditLog


def user_data(user):
    return {"id": str(user.id), "email": user.email, "username": user.username, "display_name": user.display_name, "role": user.role.value, "is_active": user.is_active}


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


async def new_session(db, user):
    sid = uuid4()
    pair = create_token_pair(str(user.id), user.email, user.role.value, str(sid))
    db.add(Session(id=sid, user_id=user.id, session_token_hash=digest(pair["refresh_token"]), expires_at=utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)))
    await db.commit()
    return {**pair, "user": user_data(user)}


async def register(db, data):
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(403, "Registration is disabled")
    # The first account boots the machine owner as ADMIN; every later sign-up is a
    # read-only VIEWER. Open registration can therefore never hand out code
    # execution (automation/recorder) or video-rendering rights.
    existing = await db.scalar(select(func.count()).select_from(User)) or 0
    role = UserRole.ADMIN if existing == 0 else UserRole.VIEWER
    user = User(id=uuid4(), email=str(data.email).lower(), username=data.username.lower(), display_name=data.display_name, password_hash=await asyncio.to_thread(hash_password, data.password), role=role)
    db.add(user)
    try:
        await db.flush()
        db.add(AuditLog(user_id=user.id, action="USER_REGISTER", result="success"))
        return await new_session(db, user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Email or username already registered")


async def login(db, data):
    user = await db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = await asyncio.to_thread(verify_password, data.password, user.password_hash) if user else False
    if not user or not valid or not user.is_active:
        raise HTTPException(401, "Invalid email or password")
    db.add(AuditLog(user_id=user.id, action="USER_LOGIN", result="success"))
    return await new_session(db, user)


async def refresh(db, token):
    payload = decode_refresh_token(token)
    try:
        sid, uid = UUID(payload["sid"]), UUID(payload["sub"])
    except (TypeError, KeyError, ValueError):
        raise HTTPException(401, "Invalid refresh token")
    user = await db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Session expired")
    pair = create_token_pair(str(uid), user.email, user.role.value, str(sid))
    result = await db.execute(update(Session).where(Session.id == sid, Session.user_id == uid, Session.revoked_at.is_(None), Session.expires_at > utcnow(), Session.session_token_hash == digest(token)).values(session_token_hash=digest(pair["refresh_token"])))
    if result.rowcount != 1:
        raise HTTPException(401, "Refresh token expired or already used")
    await db.commit()
    return {**pair, "user": user_data(user)}
