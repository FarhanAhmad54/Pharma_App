from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pharma_management.db import Base


class BatchStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    PRODUCED = "PRODUCED"
    QUARANTINED = "QUARANTINED"
    QC_TESTING = "QC_TESTING"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECALLED = "RECALLED"
    CLOSED = "CLOSED"


class ProductionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class QCStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_TESTING = "IN_TESTING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"


class MovementType(str, enum.Enum):
    PRODUCTION = "PRODUCTION"
    PURCHASE = "PURCHASE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    SALE = "SALE"
    RETURN = "RETURN"
    DAMAGE = "DAMAGE"
    EXPIRY = "EXPIRY"
    ADJUSTMENT = "ADJUSTMENT"
    RECALL = "RECALL"


class OrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    ALLOCATED = "ALLOCATED"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class ShipmentStatus(str, enum.Enum):
    PREPARING = "PREPARING"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER"
    QUALITY_MANAGER = "QUALITY_MANAGER"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    WAREHOUSE_MANAGER = "WAREHOUSE_MANAGER"
    SALES_MANAGER = "SALES_MANAGER"
    ACCOUNTANT = "ACCOUNTANT"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("sku", name="uq_products_sku"), Index("ix_products_generic_name", "generic_name"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_name: Mapped[str] = mapped_column(String(160), nullable=False)
    generic_name: Mapped[str] = mapped_column(String(160), nullable=False)
    strength: Mapped[str | None] = mapped_column(String(80))
    dosage_form: Mapped[str] = mapped_column(String(80), nullable=False)
    route: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="unit")
    packaging: Mapped[str | None] = mapped_column(String(160))
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal(0))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal(0))
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal(0))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
