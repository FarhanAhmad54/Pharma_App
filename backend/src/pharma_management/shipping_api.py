from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.db import get_db
from pharma_management.inventory_models import BatchInventory
from pharma_management.models import (
    AuditLog,
    Batch,
    BatchAllocation,
    BatchStatus,
    OrderStatus,
    SalesItem,
    SalesOrder,
    Shipment,
    ShipmentItem,
    ShipmentStatus,
    User,
    UserRole,
)
from pharma_management.security import current_user, require_roles

router = APIRouter(prefix="/api/v1")


def as_dict(obj: Any) -> dict[str, Any]:
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


@router.post(
    "/shipments/{shipment_id}/dispatch",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.SALES_MANAGER))],
)
def dispatch_shipment(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    shipment = db.scalar(select(Shipment).where(Shipment.id == shipment_id).with_for_update())
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    if shipment.status not in {ShipmentStatus.PREPARING, ShipmentStatus.READY}:
        raise HTTPException(409, f"Shipment cannot be dispatched from {shipment.status.value}")
    if not shipment.sales_order_id:
        raise HTTPException(409, "Shipment must reference a sales order")

    order = db.scalar(select(SalesOrder).where(SalesOrder.id == shipment.sales_order_id).with_for_update())
    if not order or order.status != OrderStatus.ALLOCATED:
        raise HTTPException(409, "Sales order must be ALLOCATED before dispatch")

    allocations = db.scalars(
        select(BatchAllocation)
        .join(SalesItem, SalesItem.id == BatchAllocation.sales_item_id)
        .where(SalesItem.sales_order_id == order.id)
    ).all()
    if not allocations:
        raise HTTPException(409, "Sales order has no batch allocations")

    for allocation in allocations:
        item = db.get(SalesItem, allocation.sales_item_id)
        if not item:
            raise HTTPException(409, "Allocated sales item no longer exists")
        batch = db.scalar(select(Batch).where(Batch.id == allocation.batch_id).with_for_update())
        stock = db.scalar(
            select(BatchInventory)
            .where(
                BatchInventory.batch_id == allocation.batch_id,
                BatchInventory.product_id == item.product_id,
                BatchInventory.warehouse_id == order.warehouse_id,
            )
            .with_for_update()
        )
        if not batch or not stock:
            raise HTTPException(409, "Allocated batch stock no longer exists")
        if batch.status != BatchStatus.RELEASED:
            raise HTTPException(409, "Allocated batch is no longer released")
        if stock.quantity_reserved < allocation.quantity or batch.quantity_reserved < allocation.quantity:
            raise HTTPException(409, "Reserved quantity is inconsistent")

        stock.quantity_reserved -= allocation.quantity
        batch.quantity_reserved -= allocation.quantity
        batch.quantity_sold += allocation.quantity
        db.add(
            ShipmentItem(
                shipment_id=shipment.id,
                product_id=item.product_id,
                batch_id=allocation.batch_id,
                quantity=allocation.quantity,
            )
        )

    shipment.status = ShipmentStatus.DISPATCHED
    shipment.dispatch_date = shipment.dispatch_date or datetime.now(timezone.utc)
    order.status = OrderStatus.DISPATCHED
    db.add(
        AuditLog(
            user_id=user.id,
            action="SHIPMENT_DISPATCHED",
            entity="Shipment",
            entity_id=str(shipment.id),
            reason="Allocated stock converted to shipped stock",
        )
    )
    db.commit()
    db.refresh(shipment)
    return as_dict(shipment)


@router.post(
    "/shipments/{shipment_id}/deliver",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.SALES_MANAGER))],
)
def deliver_shipment(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    shipment = db.scalar(select(Shipment).where(Shipment.id == shipment_id).with_for_update())
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    if shipment.status != ShipmentStatus.DISPATCHED:
        raise HTTPException(409, "Only dispatched shipments can be delivered")
    order = db.scalar(select(SalesOrder).where(SalesOrder.id == shipment.sales_order_id).with_for_update()) if shipment.sales_order_id else None
    if order:
        if order.status != OrderStatus.DISPATCHED:
            raise HTTPException(409, "Sales order must be DISPATCHED before delivery")
        order.status = OrderStatus.DELIVERED
    shipment.status = ShipmentStatus.DELIVERED
    shipment.delivery_date = shipment.delivery_date or datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user.id, action="SHIPMENT_DELIVERED", entity="Shipment", entity_id=str(shipment.id)))
    db.commit()
    db.refresh(shipment)
    return as_dict(shipment)
