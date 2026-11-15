"""Test support: run a service's test suite on a real PostgreSQL instead of SQLite (feature 011, T086).

SQLite does not check column lengths, hands back naive datetimes and ignores locks, so it hides defects a real database shows (a status value longer
than its column, a time zone in a hashed timestamp, a session left open in a transaction). A suite opts in with ``MMI_TEST_DATABASE_URL``:

* one throw-away schema for the whole run, built once from the service's table definitions;
* the tables are emptied between tests, after closing any session a test left open in a transaction (it would block the cleanup forever);
* the session time zone is UTC, as in production, and a lock wait fails after 15 seconds instead of hanging.

Used from a ``conftest.py``: ``eng = pg_testing.pg_engine(url, metadata)`` in the ``engine`` fixture, ``pg_testing.clean(eng, metadata)`` after the
test and ``pg_testing.drop_schema()`` once at the end of the session.
"""

from __future__ import annotations

import uuid
from typing import Any

_STATE: dict[str, Any] = {}


def pg_engine(url: str, metadata: Any) -> Any:
    from sqlalchemy import create_engine, text

    if "engine" not in _STATE:
        schema = f"t_{uuid.uuid4().hex[:12]}"
        admin = create_engine(url)
        with admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        eng = create_engine(url, connect_args={"options": f"-c search_path={schema} -c lock_timeout=15000 -c timezone=UTC"}, pool_pre_ping=True)
        metadata.create_all(eng)
        _STATE.update(engine=eng, admin=admin, schema=schema)
    return _STATE["engine"]


def clean(engine: Any, metadata: Any) -> None:
    from sqlalchemy import text

    with _STATE["admin"].begin() as c:
        c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid() AND state = 'idle in transaction'"))
    with engine.begin() as c:
        c.execute(text("TRUNCATE " + ", ".join(f'"{t.name}"' for t in metadata.sorted_tables) + " RESTART IDENTITY CASCADE"))


def schema_drift(url: str, service_dir: str, schema: str, metadata: Any, ignore_indexes: bool = False) -> list[str]:
    """What differs between a service's migrations and its table definitions (T087).

    Runs ``alembic upgrade head`` in a throw-away database and compares the result with ``metadata``: a column the code writes that the migrations
    never created, a type or length that disagrees, a nullability that differs, an index that is missing or named differently, a table on one side
    only. The version table is not part of the comparison. ``ignore_indexes=True`` leaves the indexes out.
    """
    import os
    import subprocess
    import sys

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    name = f"drift_{uuid.uuid4().hex[:10]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        dburl = make_url(url).set(database=name).render_as_string(hide_password=False)
        done = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=service_dir, env={**os.environ, "MMI_DATABASE_URL": dburl},
                              capture_output=True, text=True)
        if done.returncode != 0:
            return [f"alembic upgrade head failed: {done.stderr.strip().splitlines()[-1] if done.stderr.strip() else done.returncode}"]
        eng = create_engine(dburl, connect_args={"options": f"-c search_path={schema}"})
        with eng.connect() as conn:
            context = MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": False,
                                                              "include_object": lambda obj, name, type_, reflected, compare_to: not (type_ == "table" and name == "alembic_version")})
            diffs = [str(d) for d in compare_metadata(context, metadata) if not (ignore_indexes and isinstance(d, tuple) and d[0] in ("add_index", "remove_index"))]
        eng.dispose()
        return diffs
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def drop_schema() -> None:
    from sqlalchemy import text

    if _STATE:
        _STATE["engine"].dispose()
        with _STATE["admin"].begin() as c:
            c.execute(text(f'DROP SCHEMA "{_STATE["schema"]}" CASCADE'))
        _STATE["admin"].dispose()
        _STATE.clear()
