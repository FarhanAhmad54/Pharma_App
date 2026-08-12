"""warehouse-specific batch balances

Revision ID: 0003_batch_inventory
Revises: 0002_operations_extensions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_batch_inventory"
down_revision = "0002_operations_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_inventory",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_available", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("quantity_reserved", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "warehouse_id", name="uq_batch_inventory_batch_warehouse"),
    )
    op.create_index("ix_batch_inventory_product_warehouse", "batch_inventory", ["product_id", "warehouse_id"])
    op.create_index("ix_batch_inventory_batch", "batch_inventory", ["batch_id"])

    # Backfill existing batch balances into the authoritative warehouse table.
    op.execute(
        """
        insert into public.batch_inventory
            (id, batch_id, product_id, warehouse_id, quantity_available, quantity_reserved)
        select gen_random_uuid(), id, product_id, warehouse_id, quantity_available, quantity_reserved
        from public.batches
        where warehouse_id is not null
        on conflict (batch_id, warehouse_id) do update
          set quantity_available = excluded.quantity_available,
              quantity_reserved = excluded.quantity_reserved
        """
    )
    op.execute("alter table public.batch_inventory enable row level security")
    op.execute(
        """
        create policy batch_inventory_read on public.batch_inventory
        for select to authenticated using (true)
        """
    )
    op.execute(
        """
        create policy batch_inventory_write on public.batch_inventory
        for all to authenticated
        using (is_admin() or has_role('INVENTORY_MANAGER') or has_role('WAREHOUSE_MANAGER'))
        with check (is_admin() or has_role('INVENTORY_MANAGER') or has_role('WAREHOUSE_MANAGER'))
        """
    )


def downgrade() -> None:
    op.execute("drop policy if exists batch_inventory_write on public.batch_inventory")
    op.execute("drop policy if exists batch_inventory_read on public.batch_inventory")
    op.drop_index("ix_batch_inventory_batch", table_name="batch_inventory")
    op.drop_index("ix_batch_inventory_product_warehouse", table_name="batch_inventory")
    op.drop_table("batch_inventory")
