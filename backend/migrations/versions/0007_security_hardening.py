"""add login lockout state and make audit logs immutable

Revision ID: 0007_security_hardening
Revises: 0006_domain_invariants
"""
from alembic import op

revision = "0007_security_hardening"
down_revision = "0006_domain_invariants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table public.users add column if not exists failed_login_attempts integer not null default 0")
    op.execute("alter table public.users add column if not exists locked_until timestamptz")
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
    op.execute(
        """
        drop trigger if exists trg_audit_logs_immutable on public.audit_logs;
        create trigger trg_audit_logs_immutable
        before update or delete on public.audit_logs
        for each row execute function public.prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_audit_logs_immutable on public.audit_logs")
    op.execute("drop function if exists public.prevent_audit_log_mutation()")
    op.execute("alter table public.users drop column if exists locked_until")
    op.execute("alter table public.users drop column if exists failed_login_attempts")
