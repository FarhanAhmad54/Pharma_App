from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pharma_management.db import Base


class BatchInventory(Base):
    """Authoritative stock balance for a batch at a specific warehouse."""

    __tablename__ = "batch_inventory"
    __table_args__ = (
        UniqueConstraint("batch_id", "warehouse_id", name="uq_batch_inventory_batch_warehouse"),
        Index("ix_batch_inventory_product_warehouse", "product_id", "warehouse_id"),
        Index("ix_batch_inventory_batch", "batch_id"),
        Index("ix_batch_inventory_warehouse", "warehouse_id"),
        CheckConstraint("quantity_available >= 0 and quantity_reserved >= 0", name="ck_batch_inventory_quantities_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    quantity_available: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=Decimal("0"))
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
