"""seed governance: SKU on rows, validator and approval trail on datasets (MMI-7).

Revision ID: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seed_rows", sa.Column("sku", sa.String(60)))
    op.add_column("seed_rows", sa.Column("day_text", sa.String(40)))
    op.add_column("seed_datasets", sa.Column("validated_by", sa.String(120)))
    op.add_column("seed_datasets", sa.Column("mapping_chosen_by", sa.String(120)))
    op.add_column("seed_datasets", sa.Column("rollback_reason_code", sa.String(20)))
    op.add_column("seed_datasets", sa.Column("rollback_reason_detail", sa.String(100)))
    op.add_column("seed_datasets", sa.Column("self_activation_reason_code", sa.String(20)))
    op.add_column("seed_datasets", sa.Column("self_activation_reason_detail", sa.String(100)))


def downgrade() -> None:
    op.drop_column("seed_datasets", "self_activation_reason_detail")
    op.drop_column("seed_datasets", "self_activation_reason_code")
    op.drop_column("seed_datasets", "rollback_reason_detail")
    op.drop_column("seed_datasets", "rollback_reason_code")
    op.drop_column("seed_datasets", "mapping_chosen_by")
    op.drop_column("seed_datasets", "validated_by")
    op.drop_column("seed_rows", "day_text")
    op.drop_column("seed_rows", "sku")
