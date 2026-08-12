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
    # Fresh PostgreSQL used by CI does not provide Supabase's predefined roles/functions.
    # Create only the compatibility surface needed by the RLS policies; on Supabase these
    # objects already exist and are left unchanged where appropriate.
    op.execute("create schema if not exists auth")
    op.execute(
        """
        do $do$
        begin
            if not exists (
                select 1
                from pg_proc p
                join pg_namespace n on n.oid = p.pronamespace
                where n.nspname = 'auth' and p.proname = 'uid' and p.pronargs = 0
            ) then
                create function auth.uid() returns uuid language sql stable as $fn$select null::uuid$fn$;
            end if;
        end
        $do$;
        """
    )
    op.execute("do $$ begin if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon noinherit; end if; end $$;")
    op.execute("do $$ begin if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated noinherit; end if; end $$;")
    op.execute(
        """
        create or replace function public.is_admin() returns boolean
        language sql stable security definer set search_path = public as $$
            select exists(
                select 1 from public.profiles p
                where p.id = auth.uid() and p.active and p.role in ('SUPER_ADMIN','ADMIN')
            );
        $$;
        """
    )
    op.execute(
        """
        create or replace function public.has_role(r public.user_role) returns boolean
        language sql stable security definer set search_path = public as $$
            select exists(
                select 1 from public.profiles p
                where p.id = auth.uid() and p.active and p.role = r
            );
        $$;
        """
    )

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
    op.create_index("ix_batch_inventory_warehouse", "batch_inventory", ["warehouse_id"])

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
        using (public.is_admin() or public.has_role('INVENTORY_MANAGER') or public.has_role('WAREHOUSE_MANAGER'))
        with check (public.is_admin() or public.has_role('INVENTORY_MANAGER') or public.has_role('WAREHOUSE_MANAGER'))
        """
    )


def downgrade() -> None:
    op.execute("drop policy if exists batch_inventory_write on public.batch_inventory")
    op.execute("drop policy if exists batch_inventory_read on public.batch_inventory")
    op.drop_index("ix_batch_inventory_warehouse", table_name="batch_inventory")
    op.drop_index("ix_batch_inventory_batch", table_name="batch_inventory")
    op.drop_index("ix_batch_inventory_product_warehouse", table_name="batch_inventory")
    op.drop_table("batch_inventory")
