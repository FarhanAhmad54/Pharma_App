from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.models import (
    AuditLog,
    Batch,
    BatchStatus,
    QCRecord,
    QCStatus,
    Product,
    ProductionOrder,
    ProductionStatus,
    User,
    UserRole,
    Warehouse,
)
from pharma_management.schemas import ProductCreate, ProductUpdate


def audit(
    db: Session,
    user_id: UUID | None,
    action: str,
    entity: str,
    entity_id: str,
    old: str | None = None,
    new: str | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_type=entity,
            entity_id=entity_id,
            old_value=old,
            new_value=new,
            reason=reason,
        )
    )


def create_product(db: Session, data: ProductCreate, user: User) -> Product:
    if db.scalar(select(Product).where(Product.sku == data.sku)):
        raise HTTPException(409, "Product SKU already exists")
    product = Product(**data.model_dump())
    db.add(product)
    db.flush()
    audit(db, user.id, "PRODUCT_CREATED", "Product", str(product.id), new=product.sku)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, data: ProductUpdate, user: User) -> Product:
    old = product.sku
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    audit(db, user.id, "PRODUCT_UPDATED", "Product", str(product.id), old=old, new=product.sku)
    db.commit()
    db.refresh(product)
    return product


def create_production(db: Session, data, user: User) -> ProductionOrder:
    if not db.get(Product, data.product_id):
        raise HTTPException(404, "Product not found")
    if data.warehouse_id and not db.get(Warehouse, data.warehouse_id):
        raise HTTPException(404, "Warehouse not found")
    if db.scalar(select(ProductionOrder).where(ProductionOrder.order_number == data.order_number)):
        raise HTTPException(409, "Production order number already exists")
    order = ProductionOrder(**data.model_dump(), created_by=user.id)
    db.add(order)
    db.flush()
    audit(db, user.id, "PRODUCTION_CREATED", "ProductionOrder", str(order.id))
    db.commit()
    db.refresh(order)
    return order


def transition_production(db: Session, order: ProductionOrder, target: ProductionStatus, user: User) -> ProductionOrder:
    allowed = {
        ProductionStatus.DRAFT: {ProductionStatus.PLANNED, ProductionStatus.CANCELLED},
        ProductionStatus.PLANNED: {ProductionStatus.APPROVED, ProductionStatus.CANCELLED},
        ProductionStatus.APPROVED: {ProductionStatus.IN_PROGRESS, ProductionStatus.CANCELLED},
        ProductionStatus.IN_PROGRESS: {ProductionStatus.COMPLETED},
        ProductionStatus.COMPLETED: set(),
        ProductionStatus.CANCELLED: set(),
    }
    if target not in allowed[order.status]:
        raise HTTPException(409, f"Invalid production transition {order.status.value} -> {target.value}")
    order.status = target
    now = datetime.now(timezone.utc)
    if target == ProductionStatus.IN_PROGRESS:
        order.started_at = now
        order.production_start = now
    elif target == ProductionStatus.COMPLETED:
        order.completed_at = now
        order.production_end = now
    audit(db, user.id, f"PRODUCTION_{target.value}", "ProductionOrder", str(order.id))
    db.commit()
    db.refresh(order)
    return order


def release_batch(db: Session, batch: Batch, user: User) -> Batch:
    if batch.qc_status != QCStatus.PASSED or batch.status not in {BatchStatus.QUARANTINED, BatchStatus.QC_TESTING}:
        raise HTTPException(409, "Batch must pass QC before release")
    batch.qc_status = QCStatus.RELEASED
    batch.status = BatchStatus.RELEASED
    audit(db, user.id, "BATCH_RELEASED", "Batch", str(batch.id))
    db.commit()
    db.refresh(batch)
    return batch


def record_qc(db: Session, batch: Batch, data, user: User) -> Batch:
    if batch.status in {BatchStatus.REJECTED, BatchStatus.RECALLED, BatchStatus.EXPIRED, BatchStatus.CLOSED}:
        raise HTTPException(409, "QC cannot be recorded for a terminal batch")
    batch.status = BatchStatus.QC_TESTING
    batch.qc_status = data.result
    qc = QCRecord(
        batch_id=batch.id,
        reference_number=data.reference_number,
        test_date=data.test_date,
        tester_id=user.id,
        status=data.result,
        result=data.result,
        result_status=data.result.value,
        notes=data.notes,
    )
    db.add(qc)
    if data.result in {QCStatus.FAILED, QCStatus.REJECTED}:
        batch.status = BatchStatus.REJECTED
        batch.quantity_rejected = batch.quantity_available
        batch.quantity_available = Decimal("0")
    audit(db, user.id, "QC_RECORDED", "Batch", str(batch.id), new=data.result.value)
    db.commit()
    db.refresh(batch)
    return batch
