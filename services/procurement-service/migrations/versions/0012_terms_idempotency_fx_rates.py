"""retry-safe terms saves and cached exchange rates (MMI-6 / feature 007).

``terms_idempotency`` remembers an Idempotency-Key with the hash of the request and the version it created, so a retry returns the
same result instead of a false revision conflict. ``fx_rates`` holds EUR reference rates fetched about once a day; proposals read
only this table. Nothing here is written to the ERP; no personal or business data is stored.

Revision ID: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "terms_idempotency",
        sa.Column("scope", sa.String(40), nullable=False),            # supplier_terms / product_supplier_terms
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result_version", sa.Integer, nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope", "key", name="pk_terms_idempotency"),
    )
    op.create_index("ix_terms_idempotency_created_at", "terms_idempotency", ["created_at"])
    op.create_table(
        "fx_rates",
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("published_on", sa.Date, nullable=False),
        sa.Column("eur_per_unit", sa.Numeric(20, 12), nullable=False),            # 12 decimals: weak currencies (about 17,000 per euro) keep their accuracy
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False, server_default="ecb"),
        sa.PrimaryKeyConstraint("currency", "published_on", name="pk_fx_rates"),
    )


def downgrade() -> None:
    op.drop_table("fx_rates")
    op.drop_index("ix_terms_idempotency_created_at", table_name="terms_idempotency")
    op.drop_table("terms_idempotency")
