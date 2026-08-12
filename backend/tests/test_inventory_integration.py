from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from pharma_management.db import SessionLocal
from pharma_management.extended_models import ReturnOrder
from pharma_management.inventory_models import BatchInventory
from pharma_management.models import Batch, BatchStatus, Customer, Invoice, Product, QCStatus, User, UserRole, Warehouse
from pharma_management.operations_api import ExportCreate, create_export


def _user(suffix: str) -> User:
    return User(email=f"integration-{suffix}@example.com", full_name="Integration User", password_hash="x", role=UserRole.ADMIN)


def test_export_reconciles_batch_and_warehouse_balance() -> None:
    db = SessionLocal()
    suffix = "export"
    try:
        product = Product(
            sku=f"EXP-P-{suffix}", brand_name="Export Product", generic_name="Export Product",
            dosage_form="tablet", unit_of_measure="unit", unit="unit",
            selling_price=Decimal("10"), cost_price=Decimal("5"), reorder_threshold=Decimal("1"),
        )
        warehouse = Warehouse(code=f"EXP-WH-{suffix}", name="Export Warehouse")
        user = _user(suffix)
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
        db.commit()

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
        db.close()
