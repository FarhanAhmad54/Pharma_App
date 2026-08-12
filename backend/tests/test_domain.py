from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pharma_management.schemas import CompleteProductionRequest


def test_expiry_must_follow_manufacturing_date() -> None:
    with pytest.raises(ValidationError):
        CompleteProductionRequest(
            actual_quantity=Decimal("100"),
            batch_number="B-1",
            manufacturing_date=date(2026, 8, 12),
            expiry_date=date(2026, 8, 12),
        )


def test_valid_completion_request() -> None:
    request = CompleteProductionRequest(
        actual_quantity=Decimal("100"),
        batch_number="B-1",
        manufacturing_date=date(2026, 8, 12),
        expiry_date=date(2028, 8, 11),
    )
    assert request.actual_quantity == Decimal("100")
