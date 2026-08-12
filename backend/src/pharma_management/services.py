from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.models import (
    AuditLog,
    Batch,
    BatchAllocation,
    BatchStatus,
    Customer,
    InventoryMovement,
    MovementType,
    OrderStatus,
    Product,
    ProductionOrder,
    ProductionStatus,
    QCRecord,
    QCStatus,
    SalesItem,
    SalesOrder,
    User,
    Warehouse,
)
from pharma_management.schemas import (
    CompleteProductionRequest,
    ProductCreate,
    ProductUpdate,
    SaleCreate,
    TransferRequest,
)


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


def complete_production(db: Session, order: ProductionOrder, data: CompleteProductionRequest, user: User) -> Batch:
    if order.status != ProductionStatus.IN_PROGRESS:
        raise HTTPException(409, "Production order must be IN_PROGRESS")
    if db.scalar(select(Batch).where(Batch.batch_number == data.batch_number)):
        raise HTTPException(409, "Batch number already exists")
    if data.actual_quantity <= 0:
        raise HTTPException(422, "Actual quantity must be positive")
    if data.actual_quantity > order.planned_quantity:
        raise HTTPException(422, "Actual quantity cannot exceed planned quantity")
    if data.expiry_date <= data.manufacturing_date:
        raise HTTPException(422, "Expiry date must be after manufacturing date")
    batch = Batch(
        batch_number=data.batch_number,
        product_id=order.product_id,
        production_order_id=order.id,
        warehouse_id=order.warehouse_id,
        manufacturing_date=data.manufacturing_date,
        expiry_date=data.expiry_date,
        quantity_produced=data.actual_quantity,
        quantity_available=data.actual_quantity,
        status=BatchStatus.QUARANTINED,
        qc_status=QCStatus.PENDING,
    )
    order.actual_quantity = data.actual_quantity
    order.completed_at = datetime.now(timezone.utc)
    order.production_end = order.completed_at
    order.status = ProductionStatus.COMPLETED
    db.add(batch)
    db.flush()
    if order.warehouse_id:
        db.add(
            InventoryMovement(
                product_id=order.product_id,
                batch_id=batch.id,
                warehouse_id=order.warehouse_id,
                quantity=data.actual_quantity,
                movement_type=MovementType.PRODUCTION,
                reference_document=order.order_number,
                user_id=user.id,
                reason="Production completion",
            )
        )
    audit(db, user.id, "BATCH_CREATED", "Batch", str(batch.id), new=batch.batch_number)
    db.commit()
    db.refresh(batch)
    return batch


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


def fefo_allocate(
    db: Session,
    product_id: UUID,
    warehouse_id: UUID,
    requested: Decimal,
    user: User,
    reference: str,
) -> list[BatchAllocation]:
    if requested <= 0:
        raise HTTPException(422, "Requested quantity must be positive")
    batches = db.scalars(
        select(Batch)
        .where(
            Batch.product_id == product_id,
            Batch.warehouse_id == warehouse_id,
            Batch.status == BatchStatus.RELEASED,
            Batch.qc_status == QCStatus.RELEASED,
            Batch.expiry_date > date.today(),
            Batch.quantity_available > 0,
        )
        .order_by(Batch.expiry_date.asc(), Batch.id.asc())
        .with_for_update()
    ).all()
    remaining = requested
    allocations: list[BatchAllocation] = []
    for batch in batches:
        if remaining <= 0:
            break
        qty = min(batch.quantity_available, remaining)
        batch.quantity_available -= qty
        batch.quantity_reserved += qty
        allocations.append(BatchAllocation(batch_id=batch.id, quantity=qty))
        db.add(
            InventoryMovement(
                product_id=product_id,
                batch_id=batch.id,
                warehouse_id=warehouse_id,
                quantity=-qty,
                movement_type=MovementType.SALE,
                reference_document=reference,
                user_id=user.id,
                reason="FEFO reservation",
            )
        )
        remaining -= qty
    if remaining > 0:
        raise HTTPException(409, "Insufficient eligible released stock")
    return allocations


def create_sale(db: Session, data: SaleCreate, warehouse_id: UUID, user: User) -> SalesOrder:
    customer = db.get(Customer, data.customer_id)
    if not customer or not customer.active:
        raise HTTPException(404, "Customer not found or inactive")
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise HTTPException(404, "Warehouse not found or inactive")
    if db.scalar(select(SalesOrder).where(SalesOrder.order_number == data.order_number)):
        raise HTTPException(409, "Sales order number already exists")

    order = SalesOrder(
        order_number=data.order_number,
        customer_id=data.customer_id,
        warehouse_id=warehouse_id,
        currency=data.currency.upper(),
        created_by=user.id,
    )
    db.add(order)
    db.flush()

    subtotal = Decimal("0")
    for item_data in data.items:
        product = db.get(Product, item_data.product_id)
        if not product or not product.active:
            raise HTTPException(404, f"Product {item_data.product_id} not found or inactive")
        line_total = item_data.quantity * item_data.unit_price
        item = SalesItem(
            sales_order_id=order.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            line_total=line_total,
        )
        db.add(item)
        db.flush()
        allocations = fefo_allocate(db, item.product_id, warehouse_id, item.quantity, user, order.order_number)
        for allocation in allocations:
            allocation.sales_item_id = item.id
            db.add(allocation)
        subtotal += line_total

    order.subtotal = subtotal
    order.tax_amount = Decimal("0")
    order.total_amount = subtotal
    order.status = OrderStatus.ALLOCATED
    audit(db, user.id, "SALE_ALLOCATED", "SalesOrder", str(order.id), new=str(subtotal))
    db.commit()
    db.refresh(order)
    return order


def transfer_stock(db: Session, data: TransferRequest, user: User) -> None:
    if data.quantity <= 0:
        raise HTTPException(422, "Transfer quantity must be positive")
    if data.from_warehouse_id == data.to_warehouse_id:
        raise HTTPException(422, "Source and destination warehouses must differ")
    batch = db.scalar(select(Batch).where(Batch.id == data.batch_id).with_for_update())
    if not batch or batch.product_id != data.product_id:
        raise HTTPException(404, "Batch not found for product")
    if batch.warehouse_id != data.from_warehouse_id:
        raise HTTPException(409, "Batch is not stored in the source warehouse")
    if batch.quantity_available < data.quantity:
        raise HTTPException(409, "Insufficient available batch quantity")
    if not db.get(Warehouse, data.to_warehouse_id):
        raise HTTPException(404, "Destination warehouse not found")

    db.add(
        InventoryMovement(
            product_id=data.product_id,
            batch_id=batch.id,
            warehouse_id=data.from_warehouse_id,
            quantity=-data.quantity,
            movement_type=MovementType.TRANSFER_OUT,
            user_id=user.id,
            reason=data.reason,
        )
    )
    db.add(
        InventoryMovement(
            product_id=data.product_id,
            batch_id=batch.id,
            warehouse_id=data.to_warehouse_id,
            quantity=data.quantity,
            movement_type=MovementType.TRANSFER_IN,
            user_id=user.id,
            reason=data.reason,
        )
    )
    batch.warehouse_id = data.to_warehouse_id
    audit(db, user.id, "INVENTORY_TRANSFERRED", "Batch", str(batch.id), reason=data.reason)
    db.commit()
