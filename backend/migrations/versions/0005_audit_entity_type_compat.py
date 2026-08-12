"""ensure audit entity type is writable

Revision ID: 0005_audit_entity_type_compat
Revises: 0004_sales_warehouse_required
"""
from alembic import op

revision = "0005_audit_entity_type_compat"
down_revision = "0004_sales_warehouse_required"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table public.audit_logs
            add column if not exists entity_type text;
        """
    )
    op.execute(
        """
        update public.audit_logs
        set entity_type = coalesce(entity_type, entity, 'UNKNOWN')
        where entity_type is null;
        """
    )
    op.execute("alter table public.audit_logs alter column entity_type set default 'UNKNOWN'")
    op.execute("alter table public.audit_logs alter column entity_type set not null")


def downgrade() -> None:
    op.execute("alter table public.audit_logs alter column entity_type drop not null")
    op.execute("alter table public.audit_logs alter column entity_type drop default")
