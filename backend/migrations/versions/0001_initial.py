"""initial pharmaceutical schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supabase provides these roles, while a plain PostgreSQL CI database does not.
    # Create them only when absent so the migration is reproducible in both environments.
    bind = op.get_bind()
    bind.execute(sa.text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF; END $$;"))
    bind.execute(sa.text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF; END $$;"))

    # The canonical schema is generated from SQLAlchemy metadata. Keeping this migration
    # explicit makes deployment deterministic and gives future migrations a stable base.
    from pharma_management.db import Base
    from pharma_management import models  # noqa: F401
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from pharma_management.db import Base
    from pharma_management import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
