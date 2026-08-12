from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.db import get_db
from pharma_management.models import Customer, ExportOrder, Invoice, User
from pharma_management.extended_models import ReturnOrder
from pharma_management.operations_api import orm_dict
from pharma_management.security import current_user

router = APIRouter(prefix="/api/v1")


@router.get("/customers")
def customers(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(Customer).where(Customer.active.is_(True)).order_by(Customer.name))]


@router.get("/invoices")
def invoices(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(Invoice).order_by(Invoice.created_at.desc()).limit(200))]


@router.get("/returns")
def returns(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(ReturnOrder).order_by(ReturnOrder.created_at.desc()).limit(200))]


@router.get("/exports")
def exports(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(ExportOrder).order_by(ExportOrder.created_at.desc()).limit(200))]
