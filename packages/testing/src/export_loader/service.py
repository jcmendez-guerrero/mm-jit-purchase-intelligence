"""T033/T034/T036: the loader's orchestration, shared by the command and the local HTTP app.

``check`` validates and counts without writing. ``load`` parses, classifies rows against what earlier loads wrote, protects values
a person edited in the application, rebuilds the whole dataset and hands it to ``push`` (the Siweb mock), then records the result.
Re-running a load is safe: ids are stable, movements are unioned by content, and nothing is written twice.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import httpx

from .parse_inventory import InventoryItem, InventoryParse, parse_inventory, sku_key
from .parse_movements import Movement, MovementParse, parse_movements
from .parse_suppliers import parse_suppliers
from .push_costs import PushCosts, build_cost_rows
from .report import LoadReport
from .sku_map import SkuMap
from .store import LoaderStore
from .to_mock import build_dataset, dataset_to_json
from .to_procurement import PushLinks, PushSuppliers, build_link_rows, build_supplier_rows
from .validate_file import Limits, LoaderFileError, load_limits

Push = Callable[[dict[str, Any]], None]


class AppReader(Protocol):
    """Current values in the platform, read through its APIs with the loader principal. ``None`` means unknown."""

    def reorder_point(self, sku: str, variant_id: int) -> int | None: ...
    def link_cost(self, sku: str) -> Decimal | None: ...


class NullReader:
    def reorder_point(self, sku: str, variant_id: int) -> int | None:
        return None

    def link_cost(self, sku: str) -> Decimal | None:
        return None


def describe_failure(exc: Exception) -> str:
    """What failed, without any value from the files: the HTTP status and, for a validation refusal, the field paths and rule names only."""
    if isinstance(exc, httpx.HTTPStatusError):
        text = f"HTTP {exc.response.status_code}"
        try:
            detail = exc.response.json().get("detail")
        except Exception:
            detail = None
        if isinstance(detail, list):
            seen = []
            for d in detail[:3]:
                if isinstance(d, dict):
                    loc = ".".join(str(x) for x in d.get("loc", [])[1:])      # field path; row numbers are positions, not content
                    seen.append(f"{loc}: {d.get('type', '')}")
            if seen:
                text += " — " + "; ".join(seen)
        elif isinstance(detail, str) and detail.replace("_", "").isalnum():
            text += f" — {detail}"
        return text
    return type(exc).__name__


def _item_hash(i: InventoryItem) -> str:
    raw = json.dumps([i.name, i.category, i.brand, i.kind, i.uom, str(i.price), str(i.cost), str(i.tax_rate), i.tax_included, i.status,
                      i.available, i.reserved, i.total, i.target_stock, sorted(i.lots), i.supplier_name], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _signature(m: Movement) -> tuple:
    return (m.raw_date, m.sku, m.reason, m.quantity, m.batch, m.warehouse, m.reference)


class LoaderService:
    def __init__(self, state_dir: Path, push: Push, reader: AppReader | None = None, limits: Limits | None = None,
                 push_costs: PushCosts | None = None, push_suppliers: PushSuppliers | None = None, push_links: PushLinks | None = None) -> None:
        self.store = LoaderStore(Path(state_dir))
        self.sku_map_path = Path(state_dir) / "sku-map.json"
        self._push = push
        self._reader = reader or NullReader()
        self._limits = limits or load_limits()
        self._push_costs = push_costs
        self._push_suppliers = push_suppliers
        self._push_links = push_links
        self._checked_skus: set[str] = set()

    # ------------------------------------------------------------------ read-only
    def check(self, kind: str, filename: str, data: bytes) -> dict[str, Any]:
        if kind == "inventory":
            p = parse_inventory(data, filename, self._limits)
            self._checked_skus = set(p.items)         # a following movements check in the same run is judged against it
            return self._settle_inventory(p, self.store.last(), dry=True)
        if kind == "movements":
            known = set(self.store.inventory()) or self._checked_skus
            m = parse_movements(data, filename, self._limits, known)
            return self._settle_movements(m, self.store.movements())
        if kind == "suppliers":
            s = parse_suppliers(data, filename, self._limits)
            s.report.loaded = s.ok_rows
            return s.report.result()
        raise LoaderFileError("local_load_kind_not_available", kind)

    def differences(self) -> list[dict[str, Any]]:
        return list(self.store.last()["differences"])

    def runs(self) -> list[dict[str, Any]]:
        return list(self.store.last()["runs"])

    def review_items(self) -> list[dict[str, Any]]:
        """Rows the loader could not express in the platform's input shape, from the latest load of each kind (source: loader)."""
        latest: dict[str, dict[str, Any]] = {}
        for run in self.store.last()["runs"]:
            latest[run["kind"]] = run
        return [{"kind": kind, "row": r["row"], "code": r["code"], "detail": r.get("detail", ""), "source": "loader"}
                for kind, run in latest.items() for r in run.get("review", [])]

    def resolve_difference(self, diff_id: str, decision: str) -> None:
        last = self.store.last()
        for d in last["differences"]:
            if d["id"] == diff_id:
                d["status"] = "accepted" if decision == "accept" else "ignored"
                if decision == "accept":
                    last["accepted"].append([d["sku"], d["field"]])
                break
        else:
            raise LoaderFileError("local_load_unknown_difference", diff_id)
        self.store.save_last(last)

    def wipe(self) -> None:
        self.store.wipe()

    # ------------------------------------------------------------------ load
    def load(self, kind: str, filename: str, data: bytes, acknowledge_interpretation: bool = False) -> dict[str, Any]:
        if kind == "inventory":
            if not acknowledge_interpretation:
                raise LoaderFileError("local_load_interpretation_not_acknowledged", "Confirme la interpretación de impuestos y precios")
            return self._load_inventory(parse_inventory(data, filename, self._limits))
        if kind == "movements":
            items = self.store.inventory()
            if not items:
                raise LoaderFileError("local_load_inventory_required", "Cargue primero el inventario")
            return self._load_movements(parse_movements(data, filename, self._limits, set(items)))
        if kind == "suppliers":
            return self._load_suppliers(parse_suppliers(data, filename, self._limits))
        raise LoaderFileError("local_load_kind_not_available", kind)

    # --- inventory
    def _settle_inventory(self, p: InventoryParse, last: dict[str, Any], dry: bool = False) -> dict[str, Any]:
        loaded = updated = unchanged = 0
        for key, item in p.items.items():
            if item.kind == "service":
                continue
            old = last["item_hashes"].get(key)
            n = len(item.rows)
            if old is None:
                loaded += n
            elif old == _item_hash(item):
                unchanged += n
            else:
                updated += n
        r = p.report
        r.loaded, r.updated, r.unchanged = loaded, updated, unchanged
        return r.result()

    def _load_inventory(self, p: InventoryParse) -> dict[str, Any]:
        last = self.store.last()
        sku_map = SkuMap(self.sku_map_path)
        report = p.report
        accepted = {tuple(a) for a in last["accepted"]}
        new_diffs: list[dict[str, Any]] = []
        written = last["last_written"]
        for key, item in p.items.items():
            if item.kind != "physical":
                continue
            vid = sku_map.get_or_assign(item.sku)
            file_val = item.reorder_point
            app_val = self._reader.reorder_point(item.sku, vid)
            prev = written.get(key, {}).get("reorder_point")
            edited = app_val is not None and prev is not None and str(app_val) != prev
            if edited and app_val != file_val and (item.sku, "reorder_point") not in accepted:
                item.reorder_point = app_val                      # keep the person's value in what the sync will see
                new_diffs.append(self._diff(item.sku, "reorder_point", str(app_val), str(file_val)))
                # the last value *we* wrote stays as it was, so the person's value keeps counting as an edit
            else:
                written.setdefault(key, {})["reorder_point"] = str(item.reorder_point)
            link_cost = self._reader.link_cost(item.sku)
            if link_cost is not None and item.cost is not None and link_cost != item.cost:
                new_diffs.append(self._diff(item.sku, "cost", str(link_cost), str(item.cost)))
        result = self._settle_inventory(p, last)
        report.differences = len(new_diffs)
        result = report.result()
        # persist, rebuild and push
        self.store.save_inventory(p.items)
        last["item_hashes"] = {k: _item_hash(i) for k, i in p.items.items() if i.kind == "physical"}
        last["last_written"] = written
        last["accepted"] = [a for a in last["accepted"] if tuple(a) not in {(i.sku, "reorder_point") for i in p.items.values()}]
        open_old = [d for d in last["differences"] if d["status"] != "open"]
        last["differences"] = open_old + self._dedupe_open(last["differences"], new_diffs)
        self._rebuild_and_push(p.items, self.store.movements(), sku_map)
        last["runs"].append(result)
        self.store.save_last(last)
        step = "costes"
        try:
            if self._push_costs is not None:
                self._push_costs(build_cost_rows(p.items), result["run_id"])
            step = "enlaces con proveedores"
            link_rows = build_link_rows(p.items)
            if self._push_links is not None and link_rows:               # after the costs: a link takes its default cost from them (FR-033)
                self._push_links(link_rows)
        except (httpx.HTTPError, OSError) as exc:                       # the data is loaded; the platform refresh failed and must be seen
            raise LoaderFileError("local_load_platform_unreachable", f"No se pudo actualizar la plataforma ({step}): {describe_failure(exc)}") from exc
        return result

    # --- suppliers
    def _load_suppliers(self, p: Any) -> dict[str, Any]:
        report = p.report
        report.loaded = p.ok_rows
        if self._push_suppliers is not None and p.suppliers:
            try:
                outcome = self._push_suppliers(build_supplier_rows(p), report.run_id)
            except (httpx.HTTPError, OSError) as exc:
                raise LoaderFileError("local_load_platform_unreachable", f"No se pudieron enviar los proveedores a la plataforma: {describe_failure(exc)}") from exc
            report.unchanged = min(int(outcome.get("existing", 0)), p.ok_rows)
            report.loaded = p.ok_rows - report.unchanged
        result = report.result()
        last = self.store.last()
        last["runs"].append(result)
        self.store.save_last(last)
        return result

    # --- movements
    def _split_new(self, parsed: list[Movement], stored: list[Movement]) -> tuple[list[Movement], int]:
        have = Counter(_signature(m) for m in stored)
        seen: Counter = Counter()
        fresh: list[Movement] = []
        unchanged = 0
        for m in parsed:
            sig = _signature(m)
            seen[sig] += 1
            if seen[sig] <= have[sig]:
                unchanged += 1
            else:
                fresh.append(m)
        return fresh, unchanged

    def _settle_movements(self, m: MovementParse, stored: list[Movement]) -> dict[str, Any]:
        fresh, unchanged = self._split_new(m.movements, stored)
        m.report.loaded, m.report.unchanged = len(fresh), unchanged
        return m.report.result()

    def _load_movements(self, m: MovementParse) -> dict[str, Any]:
        stored = self.store.movements()
        fresh, _ = self._split_new(m.movements, stored)
        result = self._settle_movements(m, stored)
        merged = [*stored, *fresh]
        self.store.save_movements(merged)
        self._rebuild_and_push(self.store.inventory(), merged, SkuMap(self.sku_map_path))
        last = self.store.last()
        last["runs"].append(result)
        self.store.save_last(last)
        return result

    # --- shared
    def _rebuild_and_push(self, items: dict[str, InventoryItem], moves: list[Movement], sku_map: SkuMap) -> None:
        inv = InventoryParse(items, LoadReport(kind="inventory", file_sha256="0" * 64, rows=0), 0)
        mov = MovementParse(moves, LoadReport(kind="movements", file_sha256="0" * 64, rows=0), len(moves)) if moves else None
        ds = build_dataset(inv, mov, sku_map)
        self._push(dataset_to_json(ds))

    @staticmethod
    def _diff(sku: str, field: str, app_value: str, file_value: str) -> dict[str, Any]:
        return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sku}|{field}|{app_value}|{file_value}")), "sku": sku, "field": field,
                "app_value": app_value, "file_value": file_value, "status": "open"}

    @staticmethod
    def _dedupe_open(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
        closed_ids = {d["id"] for d in existing if d["status"] != "open"}
        return [d for d in {d["id"]: d for d in new}.values() if d["id"] not in closed_ids]


def sku_keys(items: dict[str, InventoryItem]) -> set[str]:
    return {sku_key(i.sku) for i in items.values()}
