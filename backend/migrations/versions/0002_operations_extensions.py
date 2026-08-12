"""supplier raw material and return records"""

from alembic import op

revision = "0002_operations_extensions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from pharma_management.db import Base
    from pharma_management import models  # noqa: F401
    from pharma_management import extended_models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("return_orders", "raw_materials", "suppliers"):
        bind.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}" CASCADE')
