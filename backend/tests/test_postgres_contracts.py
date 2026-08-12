from decimal import Decimal

from pharma_management.db import SessionLocal
from pharma_management.models import Customer, Product, SalesItem, SalesOrder, Warehouse


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

        order = SalesOrder(
            order_number="PG-CONTRACT-SO",
            customer_id=customer.id,
            warehouse_id=warehouse.id,
            currency="INR",
        )
        db.add(order)
        db.flush()

        item = SalesItem(
            sales_order_id=order.id,
            product_id=product.id,
            quantity=Decimal("3"),
            unit_price=Decimal("12.50"),
        )
        db.add(item)
        db.flush()

        assert item.line_total == Decimal("37.5000")
    finally:
        db.rollback()
        db.close()
