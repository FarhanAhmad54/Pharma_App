from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from pharma_management.db import SessionLocal
from pharma_management.inventory_models import BatchInventory
from pharma_management.inventory_operations import create_sale, fefo_allocate
from pharma_management.models import (
    Batch,
    BatchStatus,
    Customer,
    Product,
    QCStatus,
    SalesOrder,
    User,
    UserRole,
    Warehouse,
)
from pharma_management.operations_api import ExportCreate, create_export
from pharma_management.schemas import SaleCreate, SaleItemCreate


def _product(suffix: str) -> Product:
    return Product(
        sku=f"INT-{suffix}",
        brand_name="Integration Test",
        generic_name="Integration Test",
        dosage_form="tablet",
        unit_of_measure="unit",
        unit="unit",
        selling_price=Decimal("10.00"),
        cost_price=Decimal("5.00"),
        reorder_threshold=Decimal("1"),
    )


def _user(suffix: str) -> User:
    return User(
        email=f"integration-{suffix}@example.test",
        full_name="Integration User",
        password_hash="test-only",
        role=UserRole.SALES_MANAGER,
    )


def test_fefo_allocates_earliest_expiry_first() -> None:
    db = SessionLocal()
    try:
        suffix = uuid4().hex[:8]
        product = _product(suffix)
        warehouse = Warehouse(code=f"INT-WH-{suffix}", name="Integration Warehouse")
        user = _user(suffix)
        db.add_all([product, warehouse, user])
        db.flush()

        manufacturing = date.today()
        first = Batch(
            batch_number=f"INT-B1-{suffix}", product_id=product.id, warehouse_id=warehouse.id,
            manufacturing_date=manufacturing, expiry_date=manufacturing + timedelta(days=30),
            quantity_produced=Decimal("100"), quantity_available=Decimal("100"),
            status=BatchStatus.RELEASED, qc_status=QCStatus.RELEASED,
        )
        second = Batch(
            batch_number=f"INT-B2-{suffix}", product_id=product.id, warehouse_id=warehouse.id,
            manufacturing_date=manufacturing, expiry_date=manufacturing + timedelta(days=90),
            quantity_produced=Decimal("100"), quantity_available=Decimal("100"),
            status=BatchStatus.RELEASED, qc_status=QCStatus.RELEASED,
        )
        db.add_all([first, second])
        db.flush()
        db.add_all([
            BatchInventory(
                batch_id=first.id, product_id=product.id, warehouse_id=warehouse.id,
                quantity_available=Decimal("100"), quantity_reserved=Decimal("0"),
            ),
            BatchInventory(
                batch_id=second.id, product_id=product.id, warehouse_id=warehouse.id,
                quantity_available=Decimal("100"), quantity_reserved=Decimal("0"),
            ),
        ])
        db.flush()

        allocations = fefo_allocate(db, product.id, warehouse.id, Decimal("150"), user, "INT-FEFO")

        assert allocations == [(first.id, Decimal("100")), (second.id, Decimal("50"))]
        first_stock = db.scalar(select(BatchInventory).where(BatchInventory.batch_id == first.id))
        second_stock = db.scalar(select(BatchInventory).where(BatchInventory.batch_id == second.id))
        assert first_stock is not None and first_stock.quantity_available == Decimal("0")
        assert second_stock is not None and second_stock.quantity_available == Decimal("50")
    finally:
        db.rollback()
        db.close()


def test_failed_sale_does_not_leak_fefo_reservations() -> None:
    db = SessionLocal()
    suffix = uuid4().hex[:8]
    ids: dict[str, object] = {}
    try:
        product = _product(suffix)
        warehouse = Warehouse(code=f"RB-WH-{suffix}", name="Rollback Warehouse")
        customer = Customer(code=f"RB-CUST-{suffix}", name="Rollback Customer")
        user = _user(f"rb-{suffix}")
        db.add_all([product, warehouse, customer, user])
        db.flush()

        batch = Batch(
            batch_number=f"RB-B-{suffix}", product_id=product.id, warehouse_id=warehouse.id,
            manufacturing_date=date.today(), expiry_date=date.today() + timedelta(days=120),
            quantity_produced=Decimal("100"), quantity_available=Decimal("100"),
            status=BatchStatus.RELEASED, qc_status=QCStatus.RELEASED,
        )
        db.add(batch)
        db.flush()
        db.add(BatchInventory(
            batch_id=batch.id, product_id=product.id, warehouse_id=warehouse.id,
            quantity_available=Decimal("100"), quantity_reserved=Decimal("0"),
        ))
        db.flush()
        db.commit()

        ids.update(product=product.id, warehouse=warehouse.id, customer=customer.id, user=user.id, batch=batch.id)

        with pytest.raises(HTTPException) as exc_info:
            create_sale(
                db,
                SaleCreate(
                    order_number=f"RB-SO-{suffix}", customer_id=customer.id, currency="INR",
                    items=[SaleItemCreate(product_id=product.id, quantity=Decimal("150"), unit_price=Decimal("12.50"))],
                ),
                warehouse.id,
                user,
            )

        assert exc_info.value.status_code == 409
        stock = db.scalar(select(BatchInventory).where(BatchInventory.batch_id == batch.id))
        assert stock is not None
        assert stock.quantity_available == Decimal("100")
        assert stock.quantity_reserved == Decimal("0")
        assert db.scalar(select(SalesOrder).where(SalesOrder.order_number == f"RB-SO-{suffix}")) is None
    finally:
        db.rollback()
        cleanup = SessionLocal()
        try:
            if ids:
                cleanup.execute(delete(BatchInventory).where(BatchInventory.batch_id == ids["batch"]))
                cleanup.execute(delete(Batch).where(Batch.id == ids["batch"]))
                cleanup.execute(delete(User).where(User.id == ids["user"]))
                cleanup.execute(delete(Customer).where(Customer.id == ids["customer"]))
                cleanup.execute(delete(Product).where(Product.id == ids["product"]))
                cleanup.execute(delete(Warehouse).where(Warehouse.id == ids["warehouse"]))
                cleanup.commit()
        finally:
            cleanup.close()
        db.close()


def test_export_allocation_updates_authoritative_warehouse_stock() -> None:
    db = SessionLocal()
    suffix = uuid4().hex[:8]
    ids: dict[str, object] = {}
    try:
        product = _product(f"EXP-{suffix}")
        warehouse = Warehouse(code=f"EXP-WH-{suffix}", name="Export Warehouse")
        user = _user(f"exp-{suffix}")
        db.add_all([product, warehouse, user])
        db.flush()
        batch = Batch(
            batch_number=f"EXP-B-{suffix}", product_id=product.id, warehouse_id=warehouse.id,
            manufacturing_date=date.today(), expiry_date=date.today() + timedelta(days=180),
            quantity_produced=Decimal("100"), quantity_available=Decimal("100"),
            status=BatchStatus.RELEASED, qc_status=QCStatus.RELEASED,
        )
        db.add(batch)
        db.flush()
        db.add(BatchInventory(
            batch_id=batch.id, product_id=product.id, warehouse_id=warehouse.id,
            quantity_available=Decimal("100"), quantity_reserved=Decimal("0"),
        ))
        db.flush()
        db.commit()
        ids.update(product=product.id, warehouse=warehouse.id, user=user.id, batch=batch.id)

        result = create_export(
            ExportCreate(
                export_number=f"EXP-{suffix}", destination_country="IN", importer="Integration Importer",
                product_id=product.id, batch_id=batch.id, warehouse_id=warehouse.id,
                quantity=Decimal("40"), currency="INR", export_value=Decimal("500"),
            ),
            db,
            user,
        )
        assert result["export_number"] == f"EXP-{suffix}"

        db.expire_all()
        current_batch = db.get(Batch, batch.id)
        current_stock = db.scalar(select(BatchInventory).where(BatchInventory.batch_id == batch.id))
        assert current_batch is not None and current_batch.quantity_available == Decimal("60")
        assert current_stock is not None and current_stock.quantity_available == Decimal("60")
    finally:
        db.rollback()
        cleanup = SessionLocal()
        try:
            if ids:
                from pharma_management.models import ExportOrder, InventoryMovement

                cleanup.execute(delete(InventoryMovement).where(InventoryMovement.batch_id == ids["batch"]))
                cleanup.execute(delete(ExportOrder).where(ExportOrder.batch_id == ids["batch"]))
                cleanup.execute(delete(BatchInventory).where(BatchInventory.batch_id == ids["batch"]))
                cleanup.execute(delete(Batch).where(Batch.id == ids["batch"]))
                # Audit lineage is intentionally retained; production users are deactivated rather than hard-deleted.
                cleanup.execute(delete(Product).where(Product.id == ids["product"]))
                cleanup.execute(delete(Warehouse).where(Warehouse.id == ids["warehouse"]))
                cleanup.commit()
        finally:
            cleanup.close()
        db.close()
