"""persist revocable authentication sessions

Revision ID: 0008_auth_sessions
Revises: 0007_security_hardening
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_auth_sessions"
down_revision = "0007_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text("select to_regclass('public.auth_sessions') is not null")).scalar()
    if not exists:
        op.create_table(
            "auth_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("jti", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=1024), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("jti"),
        )
    op.execute("create index if not exists ix_auth_sessions_user_id on public.auth_sessions (user_id)")
    op.execute("create index if not exists ix_auth_sessions_jti on public.auth_sessions (jti)")
    op.execute("create index if not exists ix_auth_sessions_expires_at on public.auth_sessions (expires_at)")


def downgrade() -> None:
    op.execute("drop index if exists ix_auth_sessions_expires_at")
    op.execute("drop index if exists ix_auth_sessions_jti")
    op.execute("drop index if exists ix_auth_sessions_user_id")
    op.execute("drop table if exists public.auth_sessions")
