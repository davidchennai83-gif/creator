from datetime import datetime
from app.utils.time import utcnow
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, unavailable
from app.config.settings import settings
from app.database.engine import get_db
from app.models.user import Session, User
from app.models.system import AuditLog
from app.schemas.auth import LoginRequest, RegisterRequest, RefreshRequest
from app.schemas.common import success
from app.services import auth_service

router = APIRouter()
COOKIE_PATH = "/api/v1/auth"


def set_session(response, pair):
    response.set_cookie("refresh_token", pair["refresh_token"], httponly=True, secure=settings.COOKIE_SECURE, samesite="strict", path=COOKIE_PATH, max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    response.headers["Cache-Control"] = "no-store"
    return success(pair)


@router.post("/register", status_code=201)
async def register(data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    return set_session(response, await auth_service.register(db, data))


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    return set_session(response, await auth_service.login(db, data))


@router.post("/refresh")
async def refresh(request: Request, response: Response, data: RefreshRequest | None = None, db: AsyncSession = Depends(get_db)):
    # Browser cookie requests must be same-origin or explicitly allowed.
    if data is None:
        origin = request.headers.get("origin")
        allowed = {s.strip() for s in settings.ALLOWED_ORIGINS.split(",")} | {str(request.base_url).rstrip("/")}
        if not origin or origin not in allowed:
            raise HTTPException(403, "Origin required for cookie refresh")
    token = data.refresh_token if data else request.cookies.get("refresh_token", "")
    return set_session(response, await auth_service.refresh(db, token))


@router.post("/logout")
async def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, request.state.session_id)
    session.revoked_at = utcnow()
    db.add(AuditLog(user_id=user.id, action="USER_LOGOUT", result="success"))
    await db.commit()
    response.delete_cookie("refresh_token", path=COOKIE_PATH)
    return success(message="Logged out")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return success(auth_service.user_data(user))


@router.post("/forgot-password")
@router.post("/reset-password")
async def password_reset():
    unavailable()
