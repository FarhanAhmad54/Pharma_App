from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.config import get_settings
from pharma_management.db import get_db
from pharma_management.models import User, UserRole

password_hash = PasswordHash.recommended()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    expires = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "role": user.role.value, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), int(expires.total_seconds())


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = UUID(str(payload.get("sub")))
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_error
    user = db.get(User, user_id)
    if not user or not user.active:
        raise credentials_error
    return user


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles and user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
