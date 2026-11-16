"""censoring-rule revisions are unique per rule, scope and key (feature 011).

Saves check the revision they edited; this index makes the database refuse a second save that took the same revision at the same instant.
If an older database already holds duplicate revisions, the upgrade stops and they must be reviewed by hand; nothing is rewritten here.

Revision ID: 0010
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("uq_censoring_rules_revision", "censoring_rules", ["rule", "scope", "key", "revision"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_censoring_rules_revision", table_name="censoring_rules")
