from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pharma_management.schemas import CompleteProductionRequest, SaleCreate, SaleItemCreate, TransferRequest


def test_production_expiry_must_be_after_manufacturing_date() -> None:
    with pytest.raises(ValidationError):
        CompleteProductionRequest(
            actual_quantity=Decimal("100"),
            batch_number="B-100",
            manufacturing_date=date(2026, 8, 12),
            expiry_date=date(2026, 8, 12),
        )


def test_transfer_requires_positive_quantity_and_distinct_warehouses() -> None:
    with pytest.raises(ValidationError):
        TransferRequest(
            product_id=uuid4(),
            batch_id=uuid4(),
            from_warehouse_id=uuid4(),
            to_warehouse_id=uuid4(),
            quantity=Decimal("0"),
            reason="test",
        )


def test_sale_requires_items() -> None:
    with pytest.raises(ValidationError):
        SaleCreate(
            order_number="SO-100",
            customer_id=uuid4(),
            currency="INR",
            items=[],
        )


def test_sale_item_quantity_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SaleItemCreate(
            product_id=uuid4(),
            quantity=Decimal("0"),
            unit_price=Decimal("10"),
        )
