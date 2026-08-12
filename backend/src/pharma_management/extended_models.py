from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pharma_management.db import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RawMaterial(Base):
    __tablename__ = "raw_materials"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    material_type: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=Decimal("0"), nullable=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(16, 3), default=Decimal("0"), nullable=False)
    storage_requirements: Mapped[str | None] = mapped_column(Text)
    lot_number: Mapped[str | None] = mapped_column(String(80))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False)


class ReturnOrder(Base):
    __tablename__ = "return_orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales_orders.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    return_condition: Mapped[str] = mapped_column(String(80), nullable=False)
    inspection_result: Mapped[str | None] = mapped_column(String(80))
    disposition: Mapped[str] = mapped_column(String(80), default="QUARANTINE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
