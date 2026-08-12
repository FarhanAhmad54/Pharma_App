"""enforce non-negative pharmaceutical quantities and order totals

Revision ID: 0006_domain_invariants
Revises: 0005_audit_entity_type_compat
"""
from alembic import op
from sqlalchemy import text

revision = "0006_domain_invariants"
down_revision = "0005_audit_entity_type_compat"
branch_labels = None
depends_on = None


def _assert_no_violations(table: str, predicate: str, message: str) -> None:
    bind = op.get_bind()
    exists = bind.execute(text(f"select exists(select 1 from public.{table} where {predicate})")).scalar()
    if exists:
        raise RuntimeError(message)


def upgrade() -> None:
    _assert_no_violations(
        "batches",
        "quantity_produced < 0 or quantity_available < 0 or quantity_reserved < 0 "
        "or quantity_sold < 0 or quantity_rejected < 0 "
        "or quantity_available + quantity_reserved + quantity_sold + quantity_rejected > quantity_produced",
        "Existing batch quantities violate pharmaceutical inventory invariants.",
    )
    _assert_no_violations(
        "batch_inventory",
        "quantity_available < 0 or quantity_reserved < 0",
        "Existing warehouse inventory contains negative quantities.",
    )
    _assert_no_violations(
        "production_orders",
        "planned_quantity <= 0 or actual_quantity < 0 or actual_quantity > planned_quantity",
        "Existing production orders violate quantity invariants.",
    )
    _assert_no_violations(
        "sales_orders",
        "subtotal < 0 or tax_amount < 0 or total_amount < 0",
        "Existing sales orders contain negative monetary totals.",
    )

    op.execute(
        "alter table public.batches add constraint ck_batches_quantities_nonnegative "
        "check (quantity_produced >= 0 and quantity_available >= 0 and quantity_reserved >= 0 "
        "and quantity_sold >= 0 and quantity_rejected >= 0)"
    )
    op.execute(
        "alter table public.batches add constraint ck_batches_quantity_conservation "
        "check (quantity_available + quantity_reserved + quantity_sold + quantity_rejected <= quantity_produced)"
    )
    op.execute(
        "alter table public.batch_inventory add constraint ck_batch_inventory_quantities_nonnegative "
        "check (quantity_available >= 0 and quantity_reserved >= 0)"
    )
    op.execute(
        "alter table public.production_orders add constraint ck_production_quantities "
        "check (planned_quantity > 0 and actual_quantity >= 0 and actual_quantity <= planned_quantity)"
    )
    op.execute(
        "alter table public.sales_orders add constraint ck_sales_totals_nonnegative "
        "check (subtotal >= 0 and tax_amount >= 0 and total_amount >= 0)"
    )


def downgrade() -> None:
    op.execute("alter table public.sales_orders drop constraint if exists ck_sales_totals_nonnegative")
    op.execute("alter table public.production_orders drop constraint if exists ck_production_quantities")
    op.execute("alter table public.batch_inventory drop constraint if exists ck_batch_inventory_quantities_nonnegative")
    op.execute("alter table public.batches drop constraint if exists ck_batches_quantity_conservation")
    op.execute("alter table public.batches drop constraint if exists ck_batches_quantities_nonnegative")
