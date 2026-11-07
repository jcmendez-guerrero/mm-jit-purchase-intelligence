"""MMI 002 / ADR-019: the effective terms for a (supplier, variant) on a date, with where each value came from.

Per field, never globally: the most specific approved local value wins (product override, then supplier terms); a value the cost
record carries (ERP supplier list or manual cost entry) fills in only when no local value exists; a flagged default is the last
resort. When a local value differs from an ERP-sourced one the disagreement is reported, not hidden. A disable can be added by an
override but a disabled supplier cannot be re-enabled by one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from proposals.model import DEFAULT_LEAD_DAYS, Discount
from sqlalchemy.engine import Connection

from terms.overrides import current_override_row
from terms.service import current_row, row_to_terms

ERP_SOURCES = ("siweb_product_supplier", "siweb")


@dataclass(frozen=True)
class Effective:
    lead_time_days: int
    pack_multiple: int | None
    min_qty_units: int | None
    discounts: tuple[Discount, ...]
    payment_terms_days: int | None
    preferred: bool
    reliability: int | None
    disabled: bool
    sources: dict[str, str] = field(default_factory=dict)
    conflicts: tuple[dict[str, Any], ...] = ()
    supplier_version: int | None = None
    override_version: int | None = None
    flags: tuple[str, ...] = ()


def resolve_effective(conn: Connection, supplier_id: str, variant_id: int, as_of: datetime, erp: dict[str, Any] | None = None) -> Effective:
    """``erp`` carries the values of the cost record in use: {"source", "lead_time_days", "pack_size", "min_order_qty"}."""
    srow, orow = current_row(conn, supplier_id, as_of), current_override_row(conn, variant_id, supplier_id, as_of)
    st = None if srow is None else row_to_terms(srow)
    erp = erp or {}
    is_erp = erp.get("source") in ERP_SOURCES
    sources: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    flags: list[str] = []

    def pick(name: str, local_override: Any, local_supplier: Any, cost_value: Any, default: Any = None, erp_field: str | None = None) -> Any:
        if local_override is not None:
            sources[name], value = "override", local_override
        elif local_supplier is not None:
            sources[name], value = "supplier", local_supplier
        elif cost_value is not None:
            sources[name], value = "cost", cost_value
            return value
        else:
            sources[name], value = "default", default
            return value
        if is_erp and erp_field and erp.get(erp_field) is not None and erp[erp_field] != value:
            conflicts.append({"field": name, "erp_value": erp[erp_field], "local_value": value, "winner": "local"})
        return value

    lead = pick("lead_time_days", None if orow is None else orow.lead_time_days, None if st is None else st.lead_time_days, erp.get("lead_time_days"),
                DEFAULT_LEAD_DAYS, "lead_time_days")
    pack = pick("pack_multiple", None if orow is None else orow.pack_multiple, None, erp.get("pack_size"), None, "pack_size")
    moq = pick("min_qty_units", None if orow is None else orow.min_qty_units, None, erp.get("min_order_qty"), None, "min_order_qty")
    pay = pick("payment_terms_days", None if orow is None else orow.payment_terms_days, None if st is None else st.payment_terms_days, None)
    rel = pick("reliability", None if orow is None else orow.reliability, None if st is None else st.reliability, None)
    pref = pick("preferred", None if orow is None else orow.preferred, None if st is None else st.preferred, None, False)
    sup_disabled = bool(st and st.disabled)
    ov_disabled = bool(orow is not None and orow.disabled)
    sources["disabled"] = "supplier" if sup_disabled else "override" if ov_disabled else "default"
    sources["discounts"] = "supplier" if st and st.discounts else "default"
    if st is None:
        flags.append("no_supplier_terms")
    return Effective(int(lead), pack, moq, () if st is None else st.discounts, pay, bool(pref), rel, sup_disabled or ov_disabled, sources, tuple(conflicts),
                     None if srow is None else int(srow.version), None if orow is None else int(orow.version), tuple(flags))
