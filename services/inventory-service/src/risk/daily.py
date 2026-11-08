"""Daily risk evaluation (T112: stockout, expiry, data quality).

Evaluates stock levels against reorder points/demand, approaching lot expiries, and quarantined movements.
Outputs items adhering to the RiskList schema for the Spanish dashboard.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from db.tables import (
    ALL_WAREHOUSES,
    products,
    stock_lots,
    stock_movements,
    stock_snapshots,
    variants,
)
from sqlalchemy import func, select
from sqlalchemy.engine import Connection


def evaluate_risks(
    conn: Connection,
    warehouse_id: int | None = None,
    as_of: date | None = None,
    expiry_horizon_days: int = 60,
) -> list[dict[str, Any]]:
    today = as_of or datetime.now(UTC).date()
    risks: list[dict[str, Any]] = []

    # 1. Stockout evaluation
    # Get latest snapshot per variant for the given warehouse (or ALL_WAREHOUSES)
    target_wh = warehouse_id if warehouse_id is not None else ALL_WAREHOUSES

    # Find latest snapshot date on or before today
    latest_snap_subq = (
        select(
            stock_snapshots.c.variant_id,
            func.max(stock_snapshots.c.snapshot_date).label("max_date"),
        )
        .where(
            stock_snapshots.c.warehouse_id == target_wh,
            stock_snapshots.c.snapshot_date <= today,
        )
        .group_by(stock_snapshots.c.variant_id)
        .subquery()
    )

    snap_stmt = (
        select(
            stock_snapshots.c.variant_id,
            stock_snapshots.c.on_hand,
            stock_snapshots.c.available,
            variants.c.reorder_point,
            variants.c.sku,
        )
        .join(
            latest_snap_subq,
            (stock_snapshots.c.variant_id == latest_snap_subq.c.variant_id)
            & (stock_snapshots.c.snapshot_date == latest_snap_subq.c.max_date),
        )
        .join(variants, variants.c.external_id == stock_snapshots.c.variant_id)
        .where(stock_snapshots.c.warehouse_id == target_wh)
    )

    for row in conn.execute(snap_stmt).all():
        avail = row.available
        rop = row.reorder_point or 0
        if avail <= 0:
            risks.append({
                "variant_id": row.variant_id,
                "risk_type": "stockout",
                "explanation_key": "risk.stockout.out_of_stock",
                "params": {"available": avail, "sku": row.sku},
            })
        elif rop > 0 and avail <= rop:
            risks.append({
                "variant_id": row.variant_id,
                "risk_type": "stockout",
                "explanation_key": "risk.stockout.below_reorder_point",
                "params": {"available": avail, "reorder_point": rop, "sku": row.sku},
            })

    # 2. Expiry evaluation
    lot_stmt = (
        select(
            stock_lots.c.variant_id,
            stock_lots.c.batch_number,
            stock_lots.c.expiry_date,
            stock_lots.c.quantity,
        )
        .where(
            stock_lots.c.quantity > 0,
            stock_lots.c.expiry_date.isnot(None),
        )
    )
    if warehouse_id is not None:
        lot_stmt = lot_stmt.where(stock_lots.c.warehouse_id == warehouse_id)

    for lot in conn.execute(lot_stmt).all():
        if lot.expiry_date < today:
            risks.append({
                "variant_id": lot.variant_id,
                "risk_type": "expiry",
                "explanation_key": "risk.expiry.expired",
                "params": {
                    "batch_number": lot.batch_number,
                    "expiry_date": lot.expiry_date.isoformat(),
                    "quantity": lot.quantity,
                    "days_to_expiry": (lot.expiry_date - today).days,
                },
            })
        elif lot.expiry_date <= today + timedelta(days=expiry_horizon_days):
            risks.append({
                "variant_id": lot.variant_id,
                "risk_type": "expiry",
                "explanation_key": "risk.expiry.near",
                "params": {
                    "batch_number": lot.batch_number,
                    "expiry_date": lot.expiry_date.isoformat(),
                    "quantity": lot.quantity,
                    "days_to_expiry": (lot.expiry_date - today).days,
                },
            })

    # 3. Data quality evaluation
    # A) Quarantined movements
    quar_stmt = (
        select(
            stock_movements.c.variant_id,
            func.count(stock_movements.c.external_id).label("cnt"),
            func.max(stock_movements.c.quarantine_codes).label("codes"),
        )
        .where(stock_movements.c.quarantined.is_(True))
        .group_by(stock_movements.c.variant_id)
    )
    for q in conn.execute(quar_stmt).all():
        risks.append({
            "variant_id": q.variant_id,
            "risk_type": "data_quality",
            "explanation_key": "risk.data_quality.quarantined_movements",
            "params": {"quarantine_count": q.cnt, "codes": q.codes or ""},
        })

    # B) Active products missing VAT rate
    vat_stmt = (
        select(variants.c.external_id, products.c.name)
        .join(products, products.c.external_id == variants.c.product_id)
        .where(products.c.status == "active", products.c.vat_rate.is_(None), variants.c.is_service.is_(False))
    )
    for v in conn.execute(vat_stmt).all():
        risks.append({
            "variant_id": v.external_id,
            "risk_type": "data_quality",
            "explanation_key": "risk.data_quality.missing_vat",
            "params": {"product_name": v.name},
        })

    return risks
