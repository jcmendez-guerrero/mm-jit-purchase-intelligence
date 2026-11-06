"""Database engine for the ``bff`` schema.

Production and Compose use ``MMI_DATABASE_URL`` (role ``bff_svc``). Without it, local development and unit tests get a
process-local SQLite, which is refused in production so roles can never silently fall back to memory.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from .tables import metadata


def make_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("MMI_DATABASE_URL")
    if not url:
        if os.environ.get("MMI_ENV", "dev") == "prod":
            raise RuntimeError("MMI_DATABASE_URL is required in production: roles must be durable")
        url = "sqlite://"
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _connect(dbapi_conn, _):  # type: ignore[no-untyped-def]
            dbapi_conn.isolation_level = None

        @event.listens_for(engine, "begin")
        def _begin(conn):  # type: ignore[no-untyped-def]
            conn.exec_driver_sql("BEGIN")

        metadata.create_all(engine)
        return engine
    return create_engine(url, pool_pre_ping=True)
