"""require warehouse for sales orders

Revision ID: 0004_sales_warehouse_required
Revises: 0003_batch_inventory
"""
from alembic import op

revision = "0004_sales_warehouse_required"
down_revision = "0003_batch_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        do $do$
        begin
            if exists (
                select 1
                from information_schema.columns
                where table_schema = 'public'
                  and table_name = 'sales_orders'
                  and column_name = 'warehouse_id'
            ) then
                alter table public.sales_orders alter column warehouse_id set not null;
            end if;
        end
        $do$;
        """
    )


def downgrade() -> None:
    op.execute("alter table public.sales_orders alter column warehouse_id drop not null")
