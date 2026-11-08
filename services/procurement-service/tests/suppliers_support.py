"""Shared builders for the supplier tests (synthetic data only)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from db.tables import product_refs, proposal_lines, proposals
from sqlalchemy import insert

NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


def make_ref(conn, variant_id: int, product_id: int, sku: str, name: str = "Producto Sintetico", vat: Decimal | None = Decimal("21")) -> None:
    conn.execute(insert(product_refs).values(variant_id=variant_id, product_id=product_id, sku=sku, name=name, vat_rate=vat,
                                             vat_source="buyer" if vat is not None else None))


def open_line(conn, supplier_id: str, variant_id: int = 1, status: str = "draft", proposal_id: str | None = None) -> str:
    pid = proposal_id or str(uuid.uuid4())
    if proposal_id is None:
        conn.execute(insert(proposals).values(id=pid, week="2026-W45", status=status, created_by="buyer-1", last_edited_by="buyer-1", version=1,
                                              inputs_hash="x" * 64, rule_versions={}, solver_status="optimal", flags={}, created_at=NOW, updated_at=NOW))
    conn.execute(insert(proposal_lines).values(id=str(uuid.uuid4()), proposal_id=pid, variant_id=variant_id, product_id=variant_id, supplier_id=supplier_id, qty=6,
                                               unit_cost_with_recargo=Decimal("1.0"), line_total=Decimal("6.0"), forecast_or_policy="minmax", safety_stock=1,
                                               constraints_applied=[], risk="low", confidence="high", explanation={}, alternatives_compared=[]))
    return pid
