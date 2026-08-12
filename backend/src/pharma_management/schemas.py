from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from pharma_management.models import BatchStatus, OrderStatus, ProductionStatus, QCStatus, UserRole


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    brand_name: str = Field(min_length=1, max_length=160)
    generic_name: str = Field(min_length=1, max_length=160)
    strength: str | None = Field(default=None, max_length=80)
    dosage_form: str = Field(min_length=1, max_length=80)
    route: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=160)
    unit: str = Field(default="unit", max_length=32)
    packaging: str | None = Field(default=None, max_length=160)
    selling_price: Decimal = Field(default=Decimal("0"), ge=0)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_threshold: Decimal = Field(default=Decimal("0"), ge=0)


class ProductUpdate(ProductCreate):
    active: bool = True


class ProductOut(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.VIEWER


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    location: str | None = None
    capacity: Decimal | None = Field(default=None, ge=0)


class WarehouseOut(WarehouseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    active: bool


class ProductionCreate(BaseModel):
    order_number: str = Field(min_length=1, max_length=64)
    product_id: UUID
    planned_quantity: Decimal = Field(gt=0)
    warehouse_id: UUID | None = None
    notes: str | None = None


class ProductionOut(ProductionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actual_quantity: Decimal
    status: ProductionStatus
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    batch_number: str
    product_id: UUID
    production_order_id: UUID | None
    warehouse_id: UUID | None
    manufacturing_date: date
    expiry_date: date
    quantity_produced: Decimal
    quantity_available: Decimal
    quantity_reserved: Decimal
    quantity_sold: Decimal
    quantity_rejected: Decimal
    qc_status: QCStatus
    status: BatchStatus


class CompleteProductionRequest(BaseModel):
    actual_quantity: Decimal = Field(gt=0)
    batch_number: str = Field(min_length=1, max_length=80)
    manufacturing_date: date
    expiry_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "CompleteProductionRequest":
        if self.expiry_date <= self.manufacturing_date:
            raise ValueError("expiry_date must be after manufacturing_date")
        return self


class QCRequest(BaseModel):
    reference_number: str = Field(min_length=1, max_length=80)
    test_date: date
    result: QCStatus
    notes: str | None = None


class SaleItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class SaleCreate(BaseModel):
    order_number: str = Field(min_length=1, max_length=64)
    customer_id: UUID
    currency: str = Field(default="INR", min_length=3, max_length=3)
    items: list[SaleItemCreate] = Field(min_length=1)


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_number: str
    customer_id: UUID
    status: OrderStatus
    currency: str
    total_amount: Decimal
    created_at: datetime


class InventorySummary(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    quantity: Decimal


class TransferRequest(BaseModel):
    product_id: UUID
    batch_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    quantity: Decimal = Field(gt=0)
    reason: str | None = None
