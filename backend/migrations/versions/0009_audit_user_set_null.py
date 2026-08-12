"""preserve audit history when users are removed

Revision ID: 0009_audit_user_set_null
Revises: 0008_auth_sessions
"""
from alembic import op

revision = "0009_audit_user_set_null"
down_revision = "0008_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public.audit_logs drop constraint if exists audit_logs_user_id_fkey")
    op.execute(
        "alter table public.audit_logs add constraint audit_logs_user_id_fkey "
        "foreign key (user_id) references public.users(id) on delete set null"
    )


def downgrade() -> None:
    op.execute("alter table public.audit_logs drop constraint if exists audit_logs_user_id_fkey")
    op.execute(
        "alter table public.audit_logs add constraint audit_logs_user_id_fkey "
        "foreign key (user_id) references public.users(id)"
    )
