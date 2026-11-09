"""The import wizard API: roles, hostile files, the happy path, quarantine downloads, dry-run, rollback."""

import io
import json
from pathlib import Path

import jsonschema
import pytest
import seed_fixtures as sf
from conftest import FileStore, export_series
from db.tables import audit_events
from fastapi.testclient import TestClient
from imports_api import build_router, get_engine
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from openpyxl import load_workbook
from sqlalchemy import select
from tests_helpers import FakeSource

ROLES = {"buyer": {"viewer", "buyer"}, "admin": {"viewer", "admin"}, "viewer": {"viewer"}}


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), None)


def h(role):
    return {"Authorization": f"Bearer {role}"}


@pytest.fixture
def api(engine, tmp_path):
    app = create_service_app("forecast-service", validator=V())
    app.include_router(build_router(app))
    series = [export_series(v, [1] * 20, "new", False, ["new"]) for v in (9001, 9002, 9003, 9004, 9005)]
    app.state.series_source = FakeSource({"through_day": "2026-10-31", "series": series})
    app.state.seed_store = FileStore(tmp_path)
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def up(api, data, name="datos.csv", role="buyer"):
    return api.post("/imports", files={"file": (name, io.BytesIO(data))}, data={"name": "Hoja"}, headers=h(role))


def test_viewers_cannot_upload_validate_activate_or_roll_back(api):
    assert up(api, sf.static("valid.csv"), role="viewer").status_code == 403
    assert api.post("/imports/x/activate", headers=h("viewer")).status_code == 403
    assert api.post("/imports/rollback", headers=h("viewer")).status_code == 403
    assert api.get("/imports", headers=h("viewer")).status_code == 200                       # reading is open to any signed-in user
    assert api.get("/imports").status_code == 401


def test_hostile_files_are_refused_with_stable_codes_and_nothing_is_stored(api):
    cases = [(sf.macro_workbook(), "a.xlsx", 415), (sf.wrong_signature_xlsx(), "a.xlsx", 415), (sf.valid_xlsx(), "a.xlsm", 415), (sf.oversized_csv(6 * 1024 * 1024), "a.csv", 413),
             (sf.decompression_bomb_xlsx(64), "a.xlsx", 413)]
    for data, name, status in cases:
        r = up(api, data, name)
        assert r.status_code in (status, 415) and r.json()["detail"].startswith("import_"), name
    assert api.get("/imports", headers=h("buyer")).json()["datasets"] == []


def test_the_full_flow_template_upload_validate_quarantine_dryrun_activate_rollback(api, engine):
    t = api.get("/imports/template?format=csv", headers=h("buyer"))
    assert t.status_code == 200 and "SKU;Fecha" in t.content.decode("utf-8-sig")
    assert api.get("/imports/template?format=xlsx", headers=h("buyer")).status_code == 200
    first = up(api, sf.static("partly_invalid.csv")).json()
    assert first["missing"] == [] and first["row_count"] == 10
    v = api.post(f"/imports/{first['id']}/validate", json={"column_map": first["suggested_mapping"]}, headers=h("buyer")).json()
    assert (v["accepted"], v["quarantined"]) == (2, 8)
    q = api.get(f"/imports/{first['id']}/quarantine", headers=h("buyer")).json()["rows"]
    assert q[0] == {"row_no": 3, "reason_key": "import_unknown_sku", "params": {"sku": "EJ-9999"}}
    text = api.get(f"/imports/{first['id']}/quarantine?format=csv", headers=h("buyer")).content.decode("utf-8-sig")
    assert "El SKU no existe en el catálogo sincronizado." in text
    xl = load_workbook(io.BytesIO(api.get(f"/imports/{first['id']}/quarantine?format=xlsx", headers=h("buyer")).content)).active
    assert xl["B2"].value == "El SKU no existe en el catálogo sincronizado."
    dr = api.post(f"/imports/{first['id']}/dry-run", headers=h("buyer")).json()
    assert dr["rows"]["added"] == 2 and dr["compared_with"] is None
    with engine.connect() as c:
        assert [e.actor for e in c.execute(select(audit_events).where(audit_events.c.action == "seed.dry_run")).all()] == ["user-buyer"]
    assert api.post(f"/imports/{first['id']}/activate", headers=h("admin")).json()["status"] == "active"
    second = up(api, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-08")).json()
    api.post(f"/imports/{second['id']}/validate", json={"column_map": second["suggested_mapping"]}, headers=h("buyer"))
    assert api.post(f"/imports/{second['id']}/dry-run", headers=h("buyer")).json()["compared_with"] == first["id"]
    assert api.post(f"/imports/{second['id']}/activate", headers=h("admin")).status_code == 200
    rb = api.post("/imports/rollback", json={"reason_code": "test"}, headers=h("buyer")).json()
    assert rb["restored"] == first["id"]
    assert [d["status"] for d in api.get("/imports", headers=h("viewer")).json()["datasets"]] == ["rolled_back", "active"]


def test_refusals_during_the_flow_use_codes(api):
    first = up(api, sf.static("valid.csv")).json()
    assert api.post(f"/imports/{first['id']}/activate", headers=h("buyer")).json()["detail"] == "import_dataset_state"
    assert api.post("/imports/nope/validate", json={"column_map": {"Fecha": "day"}}, headers=h("buyer")).json()["detail"] == "import_unknown_dataset"
    assert api.post(f"/imports/{first['id']}/validate", json={"column_map": {"Fecha": "day"}}, headers=h("buyer")).json()["detail"] == "import_missing_column"
    assert api.post(f"/imports/{first['id']}/validate", json={"column_map": {"Fecha": "day", "Cantidad": "day"}}, headers=h("buyer")).status_code == 422
    assert api.post("/imports/rollback", json={"reason_code": "test"}, headers=h("buyer")).json()["detail"] == "import_dataset_state"
    mixed = up(api, sf.static("mixed_origin.csv")).json()
    assert api.post(f"/imports/{mixed['id']}/validate", json={"column_map": mixed["suggested_mapping"]}, headers=h("buyer")).json()["detail"] == "import_mixed_origin"


def test_mappings_can_be_saved_once_per_name(api):
    body = {"name": "Proveedor A", "column_map": {"Fecha": "day", "Cantidad": "quantity"}}
    assert api.post("/imports/mappings", json=body, headers=h("buyer")).status_code == 201
    assert api.post("/imports/mappings", json=body, headers=h("buyer")).json()["detail"] == "import_mapping_name_taken"
    assert api.post("/imports/mappings", json=body, headers=h("viewer")).status_code == 403
    assert api.get("/imports/mappings", headers=h("viewer")).json()["mappings"][0]["name"] == "Proveedor A"


SUMMARY_SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "packages/contracts/dto/seed_dataset_summary.v1.schema.json").read_text(encoding="utf-8"))


def test_the_dataset_list_validates_against_the_summary_schema_in_every_state(api):
    first = up(api, sf.static("valid.csv")).json()
    api.post(f"/imports/{first['id']}/validate", json={"column_map": first["suggested_mapping"]}, headers=h("buyer"))
    api.post(f"/imports/{first['id']}/activate", headers=h("admin"))
    second = up(api, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-08")).json()           # a fresh upload: not validated yet
    items = api.get("/imports", headers=h("viewer")).json()["datasets"]
    assert {i["status"] for i in items} == {"active", "uploaded"} and len(items) == 2 and second["id"] in {i["id"] for i in items}
    for item in items:
        jsonschema.validate(item, SUMMARY_SCHEMA, format_checker=jsonschema.FormatChecker())


def test_refused_activations_and_rollbacks_are_recorded_with_actor_action_and_dataset(api, caplog):
    import logging

    first = up(api, sf.static("valid.csv")).json()
    api.post(f"/imports/{first['id']}/validate", json={"column_map": first["suggested_mapping"]}, headers=h("buyer"))
    with caplog.at_level(logging.WARNING, logger="forecast.imports"):
        res = api.post(f"/imports/{first['id']}/activate", headers=h("buyer"))                    # the uploader and validator cannot approve
        assert res.status_code == 403 and res.json()["detail"] == "import_self_approval"
        assert api.post(f"/imports/{first['id']}/activate", headers=h("admin")).status_code == 200
        res = api.post("/imports/rollback", json={"reason_code": "  "}, headers=h("buyer"))
        assert res.status_code == 422 and res.json()["detail"] == "import_reason_required"
    refused = [r.getMessage() for r in caplog.records if r.getMessage().startswith("SEED_REFUSED")]
    assert refused == [
        f"SEED_REFUSED action=activate dataset={first['id']} actor=user-buyer reason=import_self_approval",
        "SEED_REFUSED action=rollback dataset=- actor=user-buyer reason=import_reason_required",
    ]
    assert not any("UPLOAD_REJECTED" in r.getMessage() for r in caplog.records)                    # these are not upload rejections


def test_an_erp_export_is_refused_at_the_door_with_a_415_and_stores_nothing(api, engine):
    from db.tables import seed_datasets

    export = "SKU;Nombre;Stock Disponible;Stock Total\nSYN-1;Producto sintético;3;3\n".encode()
    res = api.post("/imports", files={"file": ("inventario.csv", io.BytesIO(export))}, headers=h("buyer"))
    assert res.status_code == 415 and res.json()["detail"] == "import_erp_export_refused"
    with engine.connect() as c:
        assert c.execute(select(seed_datasets.c.id)).first() is None


def test_every_caller_sees_the_chosen_reason_but_only_admins_see_the_free_text_detail(api):
    """MMI-7 T076 (FR-033): the dataset list shows the reason code to everyone and the detail to admins only."""
    first = up(api, sf.static("valid.csv")).json()
    api.post(f"/imports/{first['id']}/validate", json={"column_map": first["suggested_mapping"]}, headers=h("buyer"))
    assert api.post(f"/imports/{first['id']}/activate", headers=h("admin")).status_code == 200
    rolled = api.post("/imports/rollback", json={"reason_code": "wrong_figures", "reason_detail": "Cifras erróneas del cliente García"}, headers=h("buyer"))
    assert rolled.status_code == 200
    for role in ("viewer", "buyer", "admin"):
        item = api.get("/imports", headers=h(role)).json()["datasets"][0]
        assert item["rollback_reason_code"] == "wrong_figures"
        assert ("rollback_reason_detail" in item) == (role == "admin"), role
        assert (item.get("rollback_reason_detail") == "Cifras erróneas del cliente García") == (role == "admin")
        assert "García" not in repr({k: v for k, v in item.items() if not k.endswith("_detail")})


def test_an_unknown_or_missing_reason_is_refused_with_its_own_code(api):
    first = up(api, sf.static("valid.csv")).json()
    api.post(f"/imports/{first['id']}/validate", json={"column_map": first["suggested_mapping"]}, headers=h("buyer"))
    api.post(f"/imports/{first['id']}/activate", headers=h("admin"))
    assert api.post("/imports/rollback", json={}, headers=h("buyer")).json()["detail"] == "import_reason_required"
    bad = api.post("/imports/rollback", json={"reason_code": "because"}, headers=h("buyer"))
    assert bad.status_code == 422 and bad.json()["detail"] == "import_reason_invalid"
    assert api.post("/imports/rollback", json={"reason_code": "test", "reason_detail": "x" * 101}, headers=h("buyer")).json()["detail"] == "import_reason_invalid"
