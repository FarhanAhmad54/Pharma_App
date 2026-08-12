from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pharma_management.inventory_models import BatchInventory
from pharma_management.models import (
    Batch,
    BatchStatus,
    Customer,
    InventoryMovement,
    Invoice,
    MovementType,
    OrderStatus,
    Product,
    ProductionOrder,
    ProductionStatus,
    QCStatus,
    SalesItem,
    SalesOrder,
    User,
    Warehouse,
)
from pharma_management.schemas import CompleteProductionRequest, SaleCreate, TransferRequest


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
    if not order.warehouse_id:
        raise HTTPException(409, "Production order must have a destination warehouse")
    if not db.get(Warehouse, order.warehouse_id):
        raise HTTPException(404, "Production warehouse not found")

    batch = Batch(
        batch_number=data.batch_number,
        product_id=order.product_id,
        production_order_id=order.id,
        warehouse_id=order.warehouse_id,
        manufacturing_date=data.manufacturing_date,
        expiry_date=data.expiry_date,
        quantity_produced=data.actual_quantity,
        quantity_available=data.actual_quantity,
        quantity_reserved=Decimal("0"),
        quantity_sold=Decimal("0"),
        quantity_rejected=Decimal("0"),
        status=BatchStatus.QUARANTINED,
        qc_status=QCStatus.PENDING,
    )
    order.actual_quantity = data.actual_quantity
    order.completed_at = datetime.now(timezone.utc)
    order.production_end = order.completed_at
    order.status = ProductionStatus.COMPLETED
    db.add(batch)
    db.flush()
    db.add(
        BatchInventory(
            batch_id=batch.id,
            product_id=batch.product_id,
            warehouse_id=order.warehouse_id,
            quantity_available=data.actual_quantity,
            quantity_reserved=Decimal("0"),
        )
    )
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
) -> list[tuple[UUID, Decimal]]:
    if requested <= 0:
        raise HTTPException(422, "Requested quantity must be positive")
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise HTTPException(404, "Warehouse not found or inactive")

    rows = db.scalars(
        select(BatchInventory)
        .join(Batch, Batch.id == BatchInventory.batch_id)
        .where(
            BatchInventory.product_id == product_id,
            BatchInventory.warehouse_id == warehouse_id,
            Batch.status == BatchStatus.RELEASED,
            Batch.qc_status == QCStatus.RELEASED,
            Batch.expiry_date > date.today(),
            BatchInventory.quantity_available > 0,
        )
        .order_by(Batch.expiry_date.asc(), Batch.batch_number.asc(), Batch.id.asc())
        .with_for_update()
    ).all()

    total_available = sum((row.quantity_available for row in rows), Decimal("0"))
    if total_available < requested:
        raise HTTPException(409, "Insufficient eligible released stock")

    remaining = requested
    allocations: list[tuple[UUID, Decimal]] = []
    for stock in rows:
        if remaining <= 0:
            break
        quantity = min(stock.quantity_available, remaining)
        stock.quantity_available -= quantity
        stock.quantity_reserved += quantity
        batch = db.get(Batch, stock.batch_id)
        if not batch:
            raise HTTPException(409, "Batch record no longer exists")
        if batch.quantity_available < quantity:
            raise HTTPException(409, "Batch aggregate stock is inconsistent")
        batch.quantity_available -= quantity
        batch.quantity_reserved += quantity
        allocations.append((stock.batch_id, quantity))
        db.add(
            InventoryMovement(
                product_id=product_id,
                batch_id=stock.batch_id,
                warehouse_id=warehouse_id,
                quantity=-quantity,
                movement_type=MovementType.SALE,
                reference_document=reference,
                user_id=user.id,
                reason="FEFO reservation",
            )
        )
        remaining -= quantity

    return allocations


def create_sale(db: Session, data: SaleCreate, warehouse_id: UUID, user: User) -> SalesOrder:
    customer = db.get(Customer, data.customer_id)
    if not customer or not customer.active:
        raise HTTPException(404, "Customer not found or inactive")
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise HTTPException(404, "Warehouse not found or inactive")
    if not data.items:
        raise HTTPException(422, "A sales order must contain at least one item")
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

    total = Decimal("0")
    try:
        for item_data in data.items:
            product = db.get(Product, item_data.product_id)
            if not product or not product.active:
                raise HTTPException(404, f"Product {item_data.product_id} not found or inactive")
            item = SalesItem(
                sales_order_id=order.id,
                product_id=product.id,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
            )
            db.add(item)
            db.flush()
            allocations = fefo_allocate(db, product.id, warehouse_id, item.quantity, user, order.order_number)
            for batch_id, quantity in allocations:
                db.execute(
                    text(
                        "insert into public.batch_allocations "
                        "(id, sales_item_id, batch_id, quantity) "
                        "values (gen_random_uuid(), :sales_item_id, :batch_id, :quantity)"
                    ),
                    {"sales_item_id": item.id, "batch_id": batch_id, "quantity": quantity},
                )
            total += item.quantity * item.unit_price

        order.subtotal = total
        order.tax_amount = Decimal("0")
        order.total_amount = total
        order.status = OrderStatus.ALLOCATED

        invoice = Invoice(
            invoice_number=f"INV-{order.order_number}",
            sales_order_id=order.id,
            issue_date=date.today(),
            currency=order.currency,
            subtotal=total,
            tax_amount=Decimal("0"),
            total_amount=total,
        )
        db.add(invoice)
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise


def transfer_stock(db: Session, data: TransferRequest, user: User) -> None:
    if data.from_warehouse_id == data.to_warehouse_id:
        raise HTTPException(422, "Source and destination warehouses must differ")
    if data.quantity <= 0:
        raise HTTPException(422, "Transfer quantity must be positive")
    source_warehouse = db.get(Warehouse, data.from_warehouse_id)
    destination_warehouse = db.get(Warehouse, data.to_warehouse_id)
    if not source_warehouse or not destination_warehouse or not source_warehouse.active or not destination_warehouse.active:
        raise HTTPException(404, "Source or destination warehouse not found or inactive")

    batch = db.scalar(select(Batch).where(Batch.id == data.batch_id).with_for_update())
    if not batch or batch.product_id != data.product_id:
        raise HTTPException(404, "Batch not found for product")
    if batch.status in {BatchStatus.EXPIRED, BatchStatus.REJECTED, BatchStatus.RECALLED, BatchStatus.CLOSED}:
        raise HTTPException(409, "Batch is not transferable")

    existing = db.scalars(
        select(BatchInventory)
        .where(
            BatchInventory.batch_id == data.batch_id,
            BatchInventory.product_id == data.product_id,
            BatchInventory.warehouse_id.in_([data.from_warehouse_id, data.to_warehouse_id]),
        )
        .order_by(BatchInventory.warehouse_id.asc())
        .with_for_update()
    ).all()
    rows = {row.warehouse_id: row for row in existing}
    source = rows.get(data.from_warehouse_id)
    if not source:
        raise HTTPException(404, "Batch stock not found in source warehouse")
    if source.quantity_available < data.quantity:
        raise HTTPException(409, "Insufficient available batch quantity")

    destination = rows.get(data.to_warehouse_id)
    if not destination:
        destination = BatchInventory(
            batch_id=data.batch_id,
            product_id=data.product_id,
            warehouse_id=data.to_warehouse_id,
            quantity_available=Decimal("0"),
            quantity_reserved=Decimal("0"),
        )
        db.add(destination)
        db.flush()

    source.quantity_available -= data.quantity
    destination.quantity_available += data.quantity

    db.add(
        InventoryMovement(
            product_id=data.product_id,
            batch_id=data.batch_id,
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
            batch_id=data.batch_id,
            warehouse_id=data.to_warehouse_id,
            quantity=data.quantity,
            movement_type=MovementType.TRANSFER_IN,
            user_id=user.id,
            reason=data.reason,
        )
    )
    db.commit()
