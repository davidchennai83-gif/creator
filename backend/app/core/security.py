from datetime import datetime, timedelta, timezone
from uuid import uuid4
import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from app.config.settings import settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        if encoded.startswith(("$2a$", "$2b$")):
            return len(password.encode()) <= 72 and bcrypt.checkpw(password.encode(), encoded.encode())
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError, ValueError):
        return False


def _encode(data: dict, kind: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**data, "type": kind, "iat": now, "exp": now + lifetime, "jti": str(uuid4()), "iss": "creator-platform"}
    key = settings.JWT_SECRET if kind == "access" else settings.JWT_REFRESH_SECRET
    return jwt.encode(payload, key, algorithm="HS256")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return _encode(data, "access", expires_delta if expires_delta is not None else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: dict) -> str:
    return _encode(data, "refresh", timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS))


def _decode(token: str, kind: str) -> dict | None:
    try:
        key = settings.JWT_SECRET if kind == "access" else settings.JWT_REFRESH_SECRET
        payload = jwt.decode(token, key, algorithms=["HS256"], issuer="creator-platform", options={"require": ["sub", "exp", "iat", "jti", "type"]})
        return payload if payload["type"] == kind else None
    except jwt.InvalidTokenError:
        return None


def decode_access_token(token: str) -> dict | None:
    return _decode(token, "access")


def decode_refresh_token(token: str) -> dict | None:
    return _decode(token, "refresh")


def create_token_pair(user_id: str, email: str, role: str, session_id: str) -> dict:
    data = {"sub": user_id, "sid": session_id}
    return {"access_token": create_access_token(data), "refresh_token": create_refresh_token(data), "token_type": "bearer"}
