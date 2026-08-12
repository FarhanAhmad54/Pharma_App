from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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
    selling_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    reorder_threshold: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)


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
    password: str = Field(min_length=1, max_length=128)


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
    location: str | None = Field(default=None, max_length=255)
    capacity: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=3)


class WarehouseOut(WarehouseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    active: bool


class ProductionCreate(BaseModel):
    order_number: str = Field(min_length=1, max_length=64)
    product_id: UUID
    planned_quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    warehouse_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


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
    actual_quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
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
    notes: str | None = Field(default=None, max_length=4000)


class SaleItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class SaleCreate(BaseModel):
    order_number: str = Field(min_length=1, max_length=64)
    customer_id: UUID
    currency: str = Field(default="INR", min_length=3, max_length=3)
    items: list[SaleItemCreate] = Field(min_length=1, max_length=100)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("currency must be a 3-letter ISO-style code")
        return normalized


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_number: str
    customer_id: UUID
    status: OrderStatus
    currency: str
    total_amount: Decimal
    created_at: datetime


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=4000)


class CustomerOut(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    active: bool


class InventorySummary(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    quantity: Decimal


class TransferRequest(BaseModel):
    product_id: UUID
    batch_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=3)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def warehouses_must_differ(self) -> "TransferRequest":
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("Source and destination warehouses must differ")
        return self
