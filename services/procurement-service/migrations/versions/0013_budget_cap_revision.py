"""budget-cap revisions are unique per cap (feature 011).

Budget-cap saves now check the revision they edited; this index makes the database refuse a second save that took the same revision at
the same instant. A NULL scope key (the global cap) counts as one value. If an older database already holds duplicate revisions, the
upgrade stops and they must be reviewed by hand; nothing is rewritten here.

Revision ID: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("uq_budget_caps_revision", "budget_caps", ["period", "scope", sa.text("coalesce(scope_key, '')"), "revision"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_budget_caps_revision", table_name="budget_caps")
