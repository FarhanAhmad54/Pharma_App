"""lock down auth sessions and audit trigger function search path

Revision ID: 0010_security_lockdown
Revises: 0009_audit_user_set_null
"""
from alembic import op

revision = "0010_security_lockdown"
down_revision = "0009_audit_user_set_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public.auth_sessions enable row level security")
    op.execute("revoke all on table public.auth_sessions from anon, authenticated")
    op.execute(
        """
        create or replace function public.prevent_audit_log_mutation()
        returns trigger
        language plpgsql
        security invoker
        set search_path = pg_catalog, public
        as $$
        begin
            raise exception 'audit_logs are immutable';
        end;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("grant select on table public.auth_sessions to authenticated")
    op.execute("alter table public.auth_sessions disable row level security")
    op.execute(
        """
        create or replace function public.prevent_audit_log_mutation()
        returns trigger
        language plpgsql
        as $$
        begin
            raise exception 'audit_logs are immutable';
        end;
        $$;
        """
    )
