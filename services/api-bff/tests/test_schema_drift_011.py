"""Feature 011 (T087): the service's migrations and its table definitions describe the same columns, types, lengths and nullability.

Needs a real PostgreSQL (``MMI_TEST_DATABASE_URL``): it runs ``alembic upgrade head`` in a throw-away database and compares the result with the model.
It found nothing today; it exists so that a column that disagrees with what the code writes (as `cost_write_requests.status` once did) is caught when
the migration or the model changes, not when a real database refuses a value.
"""

import os
from pathlib import Path

import pytest
from db.tables import metadata
from mmi_common import pg_testing

URL = os.environ.get("MMI_TEST_DATABASE_URL")


@pytest.mark.skipif(not URL, reason="needs a real PostgreSQL (MMI_TEST_DATABASE_URL)")
def test_the_migrations_and_the_table_definitions_agree():
    assert pg_testing.schema_drift(URL, str(Path(__file__).resolve().parents[1]), "bff", metadata) == []
