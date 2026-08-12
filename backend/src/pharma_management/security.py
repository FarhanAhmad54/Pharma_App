from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.auth_models import AuthSession
from pharma_management.config import get_settings
from pharma_management.db import get_db
from pharma_management.models import User, UserRole

password_hash = PasswordHash.recommended()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.active:
        return None
    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        return None
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
        db.commit()
        return None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)
    return user


def create_access_token(user: User) -> tuple[str, int, str]:
    settings = get_settings()
    expires = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(UTC)
    jti = uuid4().hex
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + expires,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires.total_seconds()), jti


def create_session(db: Session, user: User, jti: str, expires_at: datetime, request: Request | None = None) -> None:
    db.add(
        AuthSession(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
    )
    db.commit()


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = UUID(str(payload.get("sub")))
        jti = str(payload.get("jti"))
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise credentials_error from exc
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.jti == jti,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if not session or session.user_id != user_id:
        raise credentials_error
    user = db.get(User, user_id)
    if not user or not user.active:
        raise credentials_error
    return user


def revoke_session(db: Session, token: str) -> None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        jti = str(payload.get("jti"))
    except (jwt.PyJWTError, ValueError, TypeError):
        return
    session = db.scalar(select(AuthSession).where(AuthSession.jti == jti, AuthSession.revoked_at.is_(None)))
    if session:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles and user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
