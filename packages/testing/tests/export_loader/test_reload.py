"""T026: loading is repeatable: no duplicates, stock and descriptive data refresh, edited values are protected (FR-005, FR-034)."""

from __future__ import annotations

import csv
import io
from decimal import Decimal

import pytest
from export_loader import formats
from export_loader.service import LoaderService
from export_loader.validate_file import LoaderFileError
from generator.exports import write_exports


class Pushes:
    def __init__(self):
        self.bodies: list[dict] = []

    def __call__(self, body: dict) -> None:
        self.bodies.append(body)

    @property
    def last(self) -> dict:
        return self.bodies[-1]


class Reader:
    """Stands in for the platform APIs the loader reads current app values from."""

    def __init__(self):
        self.reorder: dict[str, int] = {}
        self.cost: dict[str, Decimal] = {}

    def reorder_point(self, sku, variant_id):
        return self.reorder.get(sku)

    def link_cost(self, sku):
        return self.cost.get(sku)


@pytest.fixture
def files(tmp_path):
    d = tmp_path / "files"
    write_exports(d, seed=42)
    return d


@pytest.fixture
def svc(tmp_path):
    push, reader = Pushes(), Reader()
    return LoaderService(tmp_path / "state", push, reader), push, reader


def load_inv(s, files, data=None, ack=True):
    return s.load("inventory", "inventario.csv", data or (files / "inventario.csv").read_bytes(), acknowledge_interpretation=ack)


def load_mov(s, files, data=None):
    return s.load("movements", "movimientos.xlsx", data or (files / "movimientos.xlsx").read_bytes())


def edit_inventory(files, fn) -> bytes:
    text = (files / "inventario.csv").read_bytes().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text, newline="")))
    fn(rows)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=formats.INVENTORY_HEADERS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def test_first_inventory_load_counts_and_balances(svc, files):
    s, push, _ = svc
    r = load_inv(s, files)
    assert r["loaded"] > 0 and r["updated"] == 0 and r["unchanged"] == 0
    assert r["loaded"] + r["updated"] + r["unchanged"] + r["quarantined"] + r["excluded"] + r["services"] == r["rows"]
    assert len(push.last["variants"]) == r["loaded"] - 1 + r["services"]  # one repeated SKU row merges into its item


def test_reloading_the_same_inventory_changes_nothing(svc, files):
    s, push, _ = svc
    first = load_inv(s, files)
    ids_before = [v["id"] for v in push.last["variants"]]
    second = load_inv(s, files)
    assert second["loaded"] == 0 and second["updated"] == 0 and second["unchanged"] == first["loaded"]
    assert [v["id"] for v in push.last["variants"]] == ids_before and len({v["id"] for v in push.last["variants"]}) == len(ids_before)


def test_stock_and_descriptive_data_are_overwritten(svc, files):
    s, push, _ = svc
    load_inv(s, files)

    def change(rows):
        rows[20].update({"Nombre": "Nombre nuevo sintetico", "Stock Total": "50", "Stock Disponible": "50", "Stock Reservado": "0", "Lote": ""})

    r = load_inv(s, files, edit_inventory(files, change))
    assert r["updated"] == 1
    assert any(v["name"] == "Nombre nuevo sintetico" for v in push.last["variants"])
    vid = next(v["id"] for v in push.last["variants"] if v["name"] == "Nombre nuevo sintetico")
    assert sum(lot["quantity"] for lot in push.last["lots"] if lot["variant_id"] == vid) == 50


def test_movements_need_the_inventory_first(svc, files):
    s, _, _ = svc
    with pytest.raises(LoaderFileError) as exc:
        load_mov(s, files)
    assert exc.value.code == "local_load_inventory_required"


def test_reloading_movements_creates_no_duplicates(svc, files):
    s, push, _ = svc
    load_inv(s, files)
    first = load_mov(s, files)
    n = len(push.last["movements"])
    second = load_mov(s, files)
    assert first["loaded"] > 0 and second["loaded"] == 0 and second["unchanged"] == first["loaded"]
    assert len(push.last["movements"]) == n
    ids = [m["id"] for m in push.last["movements"]]
    assert len(ids) == len(set(ids)) == first["loaded"]


def test_a_second_movements_file_is_merged_with_the_first(svc, files, tmp_path):
    s, push, _ = svc
    load_inv(s, files)
    first = load_mov(s, files)
    other = tmp_path / "more"
    write_exports(other, seed=42, n_movements=480)
    bigger = load_mov(s, files, (other / "movimientos.xlsx").read_bytes())
    assert bigger["loaded"] + bigger["unchanged"] + bigger["quarantined"] == bigger["rows"]
    assert len(push.last["movements"]) == first["loaded"] + bigger["loaded"]
    ids = [m["id"] for m in push.last["movements"]]
    assert len(ids) == len(set(ids))


def test_edited_reorder_point_is_kept_and_listed_as_a_difference(svc, files):
    s, push, reader = svc
    load_inv(s, files)
    victim = next(v for v in push.last["variants"] if v["reorder_point"] == 3)
    reader.reorder[victim["sku"]] = 9          # a person changed it in the app

    def change(rows):
        for r in rows:
            if r["SKU"] == victim["sku"]:
                r["Punto de Reorden"] = "5"

    res = load_inv(s, files, edit_inventory(files, change))
    assert next(v for v in push.last["variants"] if v["sku"] == victim["sku"])["reorder_point"] == 9
    assert res["differences"] == 1
    diff = s.differences()[0]
    assert (diff["sku"], diff["field"], diff["app_value"], diff["file_value"], diff["status"]) == (victim["sku"], "reorder_point", "9", "5", "open")


def test_accepting_a_difference_writes_the_file_value_next_load(svc, files):
    s, push, reader = svc
    load_inv(s, files)
    victim = next(v for v in push.last["variants"] if v["reorder_point"] == 3)
    reader.reorder[victim["sku"]] = 9
    data = edit_inventory(files, lambda rows: [r.update({"Punto de Reorden": "5"}) for r in rows if r["SKU"] == victim["sku"]])
    load_inv(s, files, data)
    s.resolve_difference(s.differences()[0]["id"], "accept")
    load_inv(s, files, data)
    assert next(v for v in push.last["variants"] if v["sku"] == victim["sku"])["reorder_point"] == 5


def test_ignoring_a_difference_keeps_the_app_value(svc, files):
    s, push, reader = svc
    load_inv(s, files)
    victim = next(v for v in push.last["variants"] if v["reorder_point"] == 3)
    reader.reorder[victim["sku"]] = 9
    data = edit_inventory(files, lambda rows: [r.update({"Punto de Reorden": "5"}) for r in rows if r["SKU"] == victim["sku"]])
    load_inv(s, files, data)
    s.resolve_difference(s.differences()[0]["id"], "ignore")
    load_inv(s, files, data)
    assert next(v for v in push.last["variants"] if v["sku"] == victim["sku"])["reorder_point"] == 9
    assert [d for d in s.differences() if d["status"] == "open"] == []


def test_a_link_cost_that_differs_from_the_file_is_listed_but_never_overwritten(svc, files):
    s, push, reader = svc
    load_inv(s, files)
    sku = push.last["variants"][0]["sku"]
    reader.cost[sku] = Decimal("99.99")
    r = load_inv(s, files)
    assert r["differences"] >= 1
    assert any(d["field"] == "cost" and d["sku"] == sku and d["app_value"] == "99.99" for d in s.differences())


def test_inventory_load_needs_the_interpretation_to_be_acknowledged(svc, files):
    s, push, _ = svc
    with pytest.raises(LoaderFileError) as exc:
        load_inv(s, files, ack=False)
    assert exc.value.code == "local_load_interpretation_not_acknowledged" and not push.bodies


def test_check_changes_nothing(svc, files):
    s, push, _ = svc
    r = s.check("inventory", "inventario.csv", (files / "inventario.csv").read_bytes())
    assert r["rows"] > 0 and not push.bodies and s.runs() == []


def test_runs_are_recorded(svc, files):
    s, _, _ = svc
    load_inv(s, files)
    assert len(s.runs()) == 1 and s.runs()[0]["kind"] == "inventory"


def test_wipe_removes_state_and_restarts_numbering(svc, files, tmp_path):
    s, push, _ = svc
    load_inv(s, files)
    s.wipe()
    assert not (tmp_path / "state").exists() or not any((tmp_path / "state").iterdir())
    load_inv(s, files)
    assert min(v["id"] for v in push.last["variants"]) == formats.SURROGATE_BASE
