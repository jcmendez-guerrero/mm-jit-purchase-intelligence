"""T104: events for proposals and orders, through the transactional outbox."""

from __future__ import annotations

import json
from typing import Any, Protocol

from db.tables import outbox
from mmi_common.bus import new_envelope
from mmi_common.outbox import enqueue
from sqlalchemy.engine import Connection

PROPOSAL_GENERATED = "procurement.proposal.generated.v1"
ORDER_CONFIRMED = "procurement.order.confirmed.v1"
WRITE_REQUESTED = "procurement.cost.write_requested.v1"
TERMS_CHANGED = "procurement.terms.changed.v1"
LOT_COST_CHANGED = "procurement.lot_cost.changed.v1"
SCENARIO_READY = "procurement.scenario.ready.v1"
SUBSCRIPTIONS = {PROPOSAL_GENERATED: ["bff-notifications"], ORDER_CONFIRMED: ["inventory-in"], WRITE_REQUESTED: ["costwriter-in"], TERMS_CHANGED: ["bff-notifications"], LOT_COST_CHANGED: ["inventory-in"], SCENARIO_READY: ["bff-notifications"]}


class BlobWriter(Protocol):
    def put(self, name: str, data: bytes) -> str: ...


def publish(conn: Connection, writer: BlobWriter, type_: str, resource_id: str, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    uri = writer.put(f"events/{type_}/{resource_id}.json", data)
    env = new_envelope(type_, resource_id, data, uri, correlation_id)
    enqueue(conn, outbox, env)
    return env


def proposal_generated(conn: Connection, writer: BlobWriter, proposal_id: str, week: str, version: int, correlation_id: str) -> dict[str, Any]:
    return publish(conn, writer, PROPOSAL_GENERATED, proposal_id, {"proposal_id": proposal_id, "week": week, "version": version}, correlation_id)


def order_confirmed(conn: Connection, writer: BlobWriter, order_id: str, proposal_id: str, supplier_id: str, lines: list[dict[str, Any]], correlation_id: str) -> dict[str, Any]:
    return publish(conn, writer, ORDER_CONFIRMED, order_id,
                   {"order_id": order_id, "proposal_id": proposal_id, "supplier_id": supplier_id, "lines": lines}, correlation_id)


def terms_changed(conn: Connection, writer: BlobWriter, scope: str, key: str, version: int, correlation_id: str) -> dict[str, Any]:
    """A terms or override version was saved. The event carries references only (scope, key, version), never the values."""
    resource = f"{scope}.{key}.{version}".replace(":", "_")
    return publish(conn, writer, TERMS_CHANGED, resource, {"scope": scope, "key": key, "version": version}, correlation_id)


def lot_cost_changed(conn: Connection, writer: BlobWriter, variant_id: int, supplier_id: str, lot: str, version: str, correlation_id: str, unit_cost: str, source: str) -> dict[str, Any]:
    """Carries the cost so inventory can value stock without calling procurement (the projection is a read-only copy)."""
    return publish(conn, writer, LOT_COST_CHANGED, f"{variant_id}.{supplier_id}.{lot}.{version}".replace(":", "_").replace("/", "_"),
                   {"variant_id": variant_id, "supplier_id": supplier_id, "lot": lot, "unit_cost": unit_cost, "source": source}, correlation_id)


def scenario_ready(conn: Connection, writer: BlobWriter, scenario_id: str, status: str, correlation_id: str) -> dict[str, Any]:
    return publish(conn, writer, SCENARIO_READY, scenario_id, {"scenario_id": scenario_id, "status": status}, correlation_id)
