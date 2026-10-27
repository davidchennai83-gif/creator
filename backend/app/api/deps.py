from app.utils.time import utcnow
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.engine import get_db
from app.core.security import decode_access_token
from app.models.user import User, Session

bearer = HTTPBearer(auto_error=False)


async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    payload = decode_access_token(credentials.credentials) if credentials else None
    try:
        user_id, session_id = UUID(payload["sub"]), UUID(payload["sid"])
    except (TypeError, KeyError, ValueError):
        raise HTTPException(401, "Please sign in", headers={"WWW-Authenticate": "Bearer"})
    session = await db.get(Session, session_id)
    user = await db.get(User, user_id)
    if not user or not user.is_active or not session or session.user_id != user_id or session.revoked_at or session.expires_at <= utcnow():
        raise HTTPException(401, "Session expired or revoked")
    request.state.session_id = session_id
    return user


def require_roles(*roles: str):
    async def dependency(user: User = Depends(get_current_user)):
        if user.role.value not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return dependency


editor = require_roles("SUPER_ADMIN", "ADMIN", "EDITOR")
admin = require_roles("SUPER_ADMIN", "ADMIN")


def unavailable():
    raise HTTPException(501, "This feature is not implemented yet")
