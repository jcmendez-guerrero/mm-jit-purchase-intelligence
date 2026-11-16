"""Local-only synthetic proposal seed (MMI-5 T035/T048, option A).

The compose stack has no real stock or forecast to plan from, so with ``MMI_DEMO_SEED=1`` (never in prod or staging) the
service plans from a small synthetic stock and forecast through the real ``InputsProvider`` and stores one draft proposal.
It writes only this service's own tables, through this service's own code. Absent from any cloud configuration (rule 7a).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import erp_supplier_links, proposals, suppliers
from proposals.generate import generate, store
from proposals.inputs import InputsProvider
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from users.directory import set_roles

SERVICE_LEVELS = ("0.85", "0.90", "0.95", "0.97", "0.99")
HORIZONS = (7, 14, 21, 28, 42)
ACTOR = "demo-seed"
# (variant_id, product_id, sku, name, on_hand, units per day, cost, supplier index)
ITEMS = (
    (9101, 9201, "SIN-001", "Producto sintetico A", 2, 2.0, "1.50", 0),
    (9102, 9202, "SIN-002", "Producto sintetico B", 0, 1.0, "4.20", 0),
    (9103, 9203, "SIN-003", "Producto sintetico C", 5, 3.0, "0.90", 1),
    (9104, 9204, "SIN-004", "Producto sintetico D", 1, 0.5, "12.00", 1),
)
# The gateway keeps the dev users in its own registry and mirrors only role changes; mirror the two dev approvers here so that
# "send for approval" (which needs another approver in this service's own directory) works on a fresh local stack.
DEV_APPROVERS = ("approver-1", "approver-2")
SUPPLIERS = ("Proveedor sintetico uno", "Proveedor sintetico dos")


def enabled(env: Mapping[str, str] | None = None) -> bool:
    import os

    e = os.environ if env is None else env
    return e.get("MMI_DEMO_SEED") == "1" and e.get("MMI_ENV", "") not in {"prod", "staging"}


class StaticSource:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def fetch(self) -> dict[str, Any]:
        return self._data


def _stock() -> dict[str, Any]:
    return {"variants": [{"variant_id": v, "product_id": p, "sku": sku, "name": name, "on_hand": on_hand, "service_level": "0.95", "lots": []}
                         for v, p, sku, name, on_hand, _r, _c, _s in ITEMS]}


def _forecast() -> dict[str, Any]:
    variants = {}
    for v, _p, _sku, _name, _oh, rate, _c, _s in ITEMS:
        horizons = {str(h): {"mean": rate * h, "quantiles": {lv: int(rate * h + 2 * (rate * h) ** 0.5) + 1 for lv in SERVICE_LEVELS}} for h in HORIZONS}
        variants[str(v)] = {"horizons": horizons, "policy": "minmax_poisson", "eligible": True}
    return {"run_id": "synthetic-run", "dataset_version_id": "synthetic-dataset", "variants": variants}


def provider() -> InputsProvider:
    return InputsProvider(StaticSource(_stock()), StaticSource(_forecast()), Decimal("1000"))


def seed(engine: Engine) -> str | None:
    """Create the synthetic suppliers, costs and one draft proposal. Does nothing when any proposal already exists."""
    with engine.begin() as conn:
        if conn.execute(select(proposals.c.id).limit(1)).first() is not None:
            return None
        for user in DEV_APPROVERS:
            set_roles(conn, user, ["viewer", "approver"], ACTOR)
        ids = []
        for n, name in enumerate(SUPPLIERS, start=9001):
            sid = str(uuid.uuid4())
            conn.execute(insert(suppliers).values(id=sid, external_contact_id=n, name=name))
            ids.append(sid)
        for _v, p, _sku, _name, _oh, _rate, cost, s in ITEMS:
            add_version(conn, NewCost(product_id=p, supplier_id=ids[s], cost_with_recargo=Decimal(cost), source="siweb_product_supplier", actor=ACTOR, pack_size=6), CostRules())
            conn.execute(insert(erp_supplier_links).values(product_id=p, supplier_id=ids[s], has_cost=True, last_seen_at=datetime.now(UTC)))
        today = datetime.now(UTC).date()
        year, week, _ = today.isocalendar()
        return store(conn, generate(provider().build(conn, today)), ACTOR, f"{year}-W{week:02d}", Decimal("1000"))
