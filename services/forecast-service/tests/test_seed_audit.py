"""MMI-7 T057 (FR-029): every seed state change, including the dry run, leaves an audit entry with actor, UTC time and version and no file contents."""

import seed_fixtures as sf
from conftest import KNOWN
from db.tables import audit_events
from seeds.lifecycle import record_dry_run, register_upload, validate_dataset
from sqlalchemy import select
from upload_settings import ParseLimits

L = ParseLimits()
SKUS = {f"EJ-{v}": v for v in KNOWN}


def test_a_dry_run_is_audited_with_actor_dataset_and_counts_but_no_rows(conn, store):
    up = register_upload(conn, store, "datos.csv", sf.static("valid.csv"), "Hoja", "buyer-1", L)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", L, sku_map=SKUS)
    result = {"dataset_id": up["id"], "compared_with": None, "rows": {"added": 5, "removed": 0, "changed": 0, "unchanged": 0}, "preview": [{"sku": "EJ-9001"}]}
    record_dry_run(conn, up["id"], "buyer-2", result)
    entry = conn.execute(select(audit_events).where(audit_events.c.action == "seed.dry_run")).one()
    text = repr(tuple(entry))
    assert entry.actor == "buyer-2" and entry.entity_id == up["id"] and '"added": 5' in text.replace("'", '"')
    assert "EJ-9001" not in text and "Hoja sintética" not in text                    # counts only: no rows, no file contents
