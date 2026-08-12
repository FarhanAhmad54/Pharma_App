from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from pharma_management.db import SessionLocal
from pharma_management.models import AuditLog, Customer, Product, SalesItem, SalesOrder, User, UserRole, Warehouse


def test_sales_item_line_total_is_database_generated() -> None:
    db = SessionLocal()
    try:
        product = Product(
            sku="PG-CONTRACT-001",
            brand_name="Contract Test",
            generic_name="Contract Test",
            dosage_form="tablet",
            unit_of_measure="unit",
            unit="unit",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            reorder_threshold=Decimal("1"),
        )
        warehouse = Warehouse(code="PG-CONTRACT-WH", name="Contract Warehouse")
        customer = Customer(code="PG-CONTRACT-CUST", name="Contract Customer")
        db.add_all([product, warehouse, customer])
        db.flush()
        order = SalesOrder(order_number="PG-CONTRACT-SO", customer_id=customer.id, warehouse_id=warehouse.id, currency="INR")
        db.add(order)
        db.flush()
        item = SalesItem(sales_order_id=order.id, product_id=product.id, quantity=Decimal("3"), unit_price=Decimal("12.50"))
        db.add(item)
        db.flush()
        assert item.line_total == Decimal("37.5000")
    finally:
        db.rollback()
        db.close()


def test_user_lockout_columns_are_persisted() -> None:
    db = SessionLocal()
    try:
        user = User(email="lockout-contract@example.com", full_name="Lockout Test", password_hash="x", role=UserRole.VIEWER)
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
    finally:
        db.rollback()
        db.close()


def test_audit_log_is_immutable() -> None:
    db = SessionLocal()
    try:
        user = User(email="audit-contract@example.com", full_name="Audit Test", password_hash="x", role=UserRole.AUDITOR)
        db.add(user)
        db.flush()
        entry = AuditLog(user_id=user.id, action="TEST", entity="Contract", entity_type="Contract", entity_id="1")
        db.add(entry)
        db.commit()
        with pytest.raises(DBAPIError):
            db.execute(select(AuditLog).where(AuditLog.id == entry.id)).scalar_one()
            entry.action = "MUTATED"
            db.commit()
        db.rollback()
        db.delete(db.get(AuditLog, entry.id))
        with pytest.raises(DBAPIError):
            db.commit()
    finally:
        db.rollback()
        db.close()
