from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.db import get_db
from pharma_management.models import User, UserRole
from pharma_management.security import current_user, require_roles

router = APIRouter(prefix="/api/v1")


def user_dict(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "active": user.active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/users", dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))])
def list_users(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [user_dict(user) for user in db.scalars(select(User).order_by(User.created_at.desc()))]
