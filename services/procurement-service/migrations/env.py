"""Alembic environment for procurement-service. Owns only schema "procurement" (constitution Principle IV)."""

import os

from alembic import context
from sqlalchemy import create_engine, text

SCHEMA = "procurement"
config = context.config
target_metadata = None  # set to the service's MetaData once models exist


def _url() -> str:
    url = os.environ.get("MMI_DATABASE_URL")
    if not url:
        raise RuntimeError("MMI_DATABASE_URL is required")
    return url


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as conn:
        # The schema is provisioned with the role (infra/postgres/init.sql or IaC); the service role
        # has no CREATE on the database, so only create it when running with a privileged role.
        exists = conn.execute(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"), {"s": SCHEMA}
        ).first()
        if not exists:
            conn.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
        conn.commit()
        context.configure(
            connection=conn, target_metadata=target_metadata, version_table_schema=SCHEMA,
            include_schemas=False, compare_type=True,
        )
        conn.execute(text(f'SET search_path TO "{SCHEMA}"'))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("offline mode is not supported; run against a database")
run_migrations_online()
