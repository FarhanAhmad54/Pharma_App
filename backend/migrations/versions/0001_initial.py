"""initial pharmaceutical schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The canonical schema is generated from SQLAlchemy metadata. Keeping this migration
    # explicit makes deployment deterministic and gives future migrations a stable base.
    from pharma_management.db import Base
    from pharma_management import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from pharma_management.db import Base
    from pharma_management import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
