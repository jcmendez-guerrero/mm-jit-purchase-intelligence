"""model_registry.adopted_for_segment holds a comma-separated list of patterns (found on real PostgreSQL: 14 characters was too short).

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("model_registry", "adopted_for_segment", existing_type=sa.String(14), type_=sa.String(120))


def downgrade() -> None:
    op.alter_column("model_registry", "adopted_for_segment", existing_type=sa.String(120), type_=sa.String(14))
