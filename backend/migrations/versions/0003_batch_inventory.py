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
    op.execute("create schema if not exists auth")
    op.execute(
        """
        do $do$
        begin
            if not exists (
                select 1 from pg_proc p
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
        do $role$
        begin
            if not exists (
                select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
                where n.nspname = 'public' and t.typname = 'user_role'
            ) then
                create type public.user_role as enum (
                    'SUPER_ADMIN', 'ADMIN', 'PRODUCTION_MANAGER', 'QUALITY_MANAGER',
                    'INVENTORY_MANAGER', 'WAREHOUSE_MANAGER', 'SALES_MANAGER',
                    'ACCOUNTANT', 'AUDITOR', 'VIEWER'
                );
            end if;
        end
        $role$;
        """
    )

    op.execute(
        """
        do $profile$
        begin
            if to_regclass('public.profiles') is null then
                create table public.profiles (
                    id uuid primary key,
                    email text not null,
                    full_name text not null,
                    role public.user_role not null default 'VIEWER',
                    active boolean not null default true,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                );
            end if;
        end
        $profile$;
        """
    )

    op.execute(
        """
        create or replace function public.is_admin() returns boolean
        language sql stable security definer set search_path = public as $$
            select exists(select 1 from public.profiles p where p.id = auth.uid() and p.active and p.role in ('SUPER_ADMIN','ADMIN'));
        $$;
        """
    )
    op.execute(
        """
        create or replace function public.has_role(r public.user_role) returns boolean
        language sql stable security definer set search_path = public as $$
            select exists(select 1 from public.profiles p where p.id = auth.uid() and p.active and p.role = r);
        $$;
        """
    )

    bind = op.get_bind()
    if not bind.execute(sa.text("select to_regclass('public.batch_inventory') is not null")).scalar():
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

    op.execute("create index if not exists ix_batch_inventory_product_warehouse on public.batch_inventory (product_id, warehouse_id)")
    op.execute("create index if not exists ix_batch_inventory_batch on public.batch_inventory (batch_id)")
    op.execute("create index if not exists ix_batch_inventory_warehouse on public.batch_inventory (warehouse_id)")

    op.execute(
        """
        insert into public.batch_inventory
            (id, batch_id, product_id, warehouse_id, quantity_available, quantity_reserved)
        select gen_random_uuid(), id, product_id, warehouse_id, quantity_available, quantity_reserved
        from public.batches
        where warehouse_id is not null
        on conflict (batch_id, warehouse_id) do nothing
        """
    )
    op.execute("alter table public.batch_inventory enable row level security")
    op.execute(
        """
        do $policy$
        begin
            if not exists (select 1 from pg_policies where schemaname='public' and tablename='batch_inventory' and policyname='batch_inventory_read') then
                create policy batch_inventory_read on public.batch_inventory for select to authenticated using (true);
            end if;
            if not exists (select 1 from pg_policies where schemaname='public' and tablename='batch_inventory' and policyname='batch_inventory_write') then
                create policy batch_inventory_write on public.batch_inventory
                for all to authenticated
                using (public.is_admin() or public.has_role('INVENTORY_MANAGER') or public.has_role('WAREHOUSE_MANAGER'))
                with check (public.is_admin() or public.has_role('INVENTORY_MANAGER') or public.has_role('WAREHOUSE_MANAGER'));
            end if;
        end
        $policy$;
        """
    )


def downgrade() -> None:
    op.execute("drop policy if exists batch_inventory_write on public.batch_inventory")
    op.execute("drop policy if exists batch_inventory_read on public.batch_inventory")
    op.execute("drop index if exists ix_batch_inventory_warehouse")
    op.execute("drop index if exists ix_batch_inventory_batch")
    op.execute("drop index if exists ix_batch_inventory_product_warehouse")
    op.execute("drop table if exists public.batch_inventory")
