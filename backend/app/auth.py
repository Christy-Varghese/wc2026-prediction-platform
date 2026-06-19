"""JWT admin authentication.

Single admin (env-configured) by default; if a users table is seeded it can
authenticate DB users too. Protect admin routes with `Depends(require_admin)`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/admin/login")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)


def authenticate(username: str, password: str) -> bool:
    return (username == settings.admin_username
            and password == settings.admin_password)


def create_token(sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": sub, "exp": exp}, settings.jwt_secret,
                      algorithm=settings.jwt_algorithm)


def require_admin(token: str = Depends(oauth2)) -> str:
    cred_err = HTTPException(status.HTTP_401_UNAUTHORIZED,
                             "Invalid or expired admin token",
                             {"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret,
                             algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise cred_err
    sub = payload.get("sub")
    if not sub:
        raise cred_err
    return sub
