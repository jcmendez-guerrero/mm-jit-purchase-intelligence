"""T147: assemble ProposalInputs from the other services' read APIs and this service's own data.

* inventory-service  /export/stock      stock position, lots, classification, service-level target, clinical-critical flag
* forecast-service   /forecasts/latest  point forecast and quantiles per horizon, or the conservative min/max
* procurement DB                        usable costs (with provenance), supplier terms, confirmed inbound orders
Variants without a usable cost cannot be ordered; they are reported (FR-041), never guessed.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import httpx
from costs.resolve import resolve_cost
from costs.rules import load_rules
from db.tables import product_refs, supplier_costs, supplier_review_items, suppliers
from fx.rates import convert, latest_rate, rate_state
from orders.confirm import open_inbound
from policies.overrides import effective_overrides
from policies.service import budget_versions, effective_weekly_budget_with_source, resolve_policy, supplier_weekly_budgets
from policies.stocking import MONTHLY_CHECK_DAYS, last_order_dates, stocking_map
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from suppliers.service import add_review_item
from terms.resolve import resolve_effective
from terms.schedule import order_date_from
from terms.service import current_row, row_to_terms

from proposals.model import (
    Forecast,
    HorizonForecast,
    Offer,
    ProposalInputs,
    SupplierTermsIn,
    VariantInput,
)

EXPIRY_WINDOW_DAYS = 14


class InputsUnavailableError(Exception):
    """A required upstream (stock snapshot or forecast) has nothing to offer yet."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class JsonSource(Protocol):
    def fetch(self) -> dict[str, Any]: ...


class HttpJsonSource:
    def __init__(self, url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._url, self._token, self._client = url, token, client or httpx.Client(timeout=120)

    def fetch(self) -> dict[str, Any]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(self._url, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 404:
            raise InputsUnavailableError("no_forecast")
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "HttpJsonSource(token=***)"


def to_forecast(entry: dict[str, Any]) -> Forecast:
    horizons = {int(h): HorizonForecast(v.get("mean"), {k: int(q) for k, q in v["quantiles"].items()}) for h, v in entry["horizons"].items()}
    return Forecast(horizons, entry["policy"], bool(entry["eligible"]), tuple(entry.get("reasons") or ()))


def refresh_product_refs(conn: Connection, variants: list[dict[str, Any]]) -> int:
    """Keep the variant -> product map, SKU and name current for exports. The buyer-maintained VAT rate is never touched."""
    n = 0
    for v in variants:
        if v.get("product_id") is None:
            continue
        values = {"product_id": int(v["product_id"]), "sku": v.get("sku"), "name": v.get("name")}
        if conn.execute(select(product_refs.c.variant_id).where(product_refs.c.variant_id == v["variant_id"])).first() is None:
            conn.execute(insert(product_refs).values(variant_id=int(v["variant_id"]), **values))
        else:
            conn.execute(update(product_refs).where(product_refs.c.variant_id == v["variant_id"]).values(**values))
        n += 1
    return n


def _flag_fx(conn: Connection, code: str, supplier_id: str, currency: str, now: datetime) -> None:
    """One open review item per supplier, problem and currency, however many builds see it (the screen explains the code, the detail is the currency)."""
    open_item = conn.execute(select(supplier_review_items.c.id).where(
        supplier_review_items.c.kind == code, supplier_review_items.c.supplier_id == supplier_id, supplier_review_items.c.detail == currency,
        supplier_review_items.c.status == "open")).first()
    if open_item is None:
        add_review_item(conn, code, supplier_id, currency, now)


@dataclass
class InputsReport:
    variants: int = 0
    without_forecast: list[int] = field(default_factory=list)
    without_cost: list[int] = field(default_factory=list)
    disabled_pairs: list[tuple[int, str]] = field(default_factory=list)      # (variant_id, supplier_id) removed by a manual disable
    on_request: list[int] = field(default_factory=list)                      # stocking mode "on request": never proposed
    always_stocked_unserved: list[int] = field(default_factory=list)         # always-stocked but no supplier can serve it: shown, not hidden
    fx_excluded: list[tuple[int, str, str]] = field(default_factory=list)    # (variant_id, supplier_id, fx_rate_missing / fx_rate_stale): no usable exchange rate (MMI-6)


@dataclass
class InputsProvider:
    stock: JsonSource
    forecast: JsonSource
    budget: Decimal | None = None
    expiry_window_days: int = EXPIRY_WINDOW_DAYS
    report: InputsReport = field(default_factory=InputsReport)

    def build(self, conn: Connection, today: date) -> ProposalInputs:
        stock, fc = self.stock.fetch(), self.forecast.fetch()
        if not stock.get("variants"):
            raise InputsUnavailableError("no_stock_snapshot")
        refresh_product_refs(conn, stock["variants"])
        rules, now = load_rules(conn), datetime.now().astimezone()
        inbound = open_inbound(conn, today)
        names = {r.id for r in conn.execute(select(suppliers.c.id)).all()}
        blocked = {r.id for r in conn.execute(select(suppliers.c.id).where((suppliers.c.status != "active") | (suppliers.c.classification == "non_purchasing"))).all()}
        report = InputsReport(variants=len(stock["variants"]))
        out: list[VariantInput] = []
        stocking = stocking_map(conn)
        overrides = effective_overrides(conn)
        last_bought = last_order_dates(conn)
        policy_versions: dict[str, Any] = {}
        used_suppliers: set[str] = set()
        overrides_used: dict[str, dict[str, int]] = {}
        for v in stock["variants"]:
            vid, pid = int(v["variant_id"]), v.get("product_id")
            if pid is None:
                continue
            mode, floor = stocking.get(vid, ("standard", 0))
            if mode == "on_request":
                report.on_request.append(vid)
                continue
            entry = fc["variants"].get(str(vid))
            if entry is None and mode != "always_stocked":
                report.without_forecast.append(vid)
                continue
            offers: list[Offer] = []
            cands = {r.supplier_id for r in conn.execute(select(supplier_costs.c.supplier_id).where(
                supplier_costs.c.product_id == pid, supplier_costs.c.superseded_by.is_(None), (supplier_costs.c.variant_id.is_(None)) | (supplier_costs.c.variant_id == vid))).all()}
            for sid in sorted(cands & names):
                if sid in blocked:                                  # deactivated or non-purchasing suppliers are never proposed (FR-017)
                    report.disabled_pairs.append((vid, sid))
                    continue
                res = resolve_cost(conn, int(pid), sid, rules, vid, now)
                if res.cost is None:
                    continue
                c = res.cost
                eff = resolve_effective(conn, sid, vid, now, erp={"source": c.source, "lead_time_days": c.lead_time_days, "pack_size": c.pack_size,
                                                                  "min_order_qty": c.min_order_qty})
                if eff.disabled:                                    # a manual disable removes the offer; the report says so
                    report.disabled_pairs.append((vid, sid))
                    continue
                unit_cost, fx_info = Decimal(str(c.cost_with_recargo)), ()
                if c.currency != "EUR":                             # MMI-6 FR-035: stored ECB rate for the proposal date, or the supplier stays out and is flagged
                    rate = latest_rate(conn, c.currency, today)
                    state = rate_state(rate, today)
                    if rate is None or state != "ok":
                        report.fx_excluded.append((vid, sid, f"fx_rate_{state}"))
                        _flag_fx(conn, f"fx_rate_{state}", sid, c.currency, now)
                        continue
                    fx_info = (("fx", (("currency", c.currency), ("original_cost", str(unit_cost.quantize(Decimal("0.0001")))),
                                       ("eur_per_unit", format(rate.eur_per_unit.normalize(), "f")), ("published_on", rate.published_on.isoformat()))),)
                    unit_cost = convert(unit_cost, rate)
                info = (("supplier_version", eff.supplier_version), ("override_version", eff.override_version), ("sources", tuple(sorted(eff.sources.items()))),
                        ("conflicts", tuple(tuple(sorted(x.items())) for x in eff.conflicts)), *fx_info)
                offers.append(Offer(sid, unit_cost, c.id, c.source, res.status, eff.pack_multiple or 1, eff.lead_time_days,
                                    eff.min_qty_units or 0, eff.preferred, info))
                used_suppliers.add(sid)
                if eff.override_version is not None:
                    overrides_used.setdefault(sid, {})[str(vid)] = eff.override_version
            if not offers:
                report.without_cost.append(vid)
                if mode == "always_stocked":
                    report.always_stocked_unserved.append(vid)
                continue
            forecast = to_forecast(entry) if entry is not None else Forecast({}, "always_stocked_floor", False, ("no_forecast",))
            horizon_mean = {h: hf.mean for h, hf in forecast.horizons.items() if hf.mean is not None}
            soon = max(math.ceil(horizon_mean.get(14, 0.0) - horizon_mean.get(7, 0.0)), 0) if forecast.eligible and horizon_mean else 0
            cutoff = today + timedelta(days=self.expiry_window_days)
            expiring = sum(int(x["quantity"]) for x in v.get("lots", []) if x.get("expiry_date") and date.fromisoformat(x["expiry_date"]) <= cutoff)
            seg = v.get("segment") or {}
            segments = tuple(x for x in (("critical",) if v.get("clinical_critical") else ()) + ((seg.get("abc"),) if seg.get("abc") else ())
                             + (("sparse",) if seg.get("pattern") in ("intermittent", "lumpy") else ()) if x)
            pol = resolve_policy(conn, vid, segments, today)
            policy_versions.update(pol.revisions)
            bought = last_bought.get(vid)
            monthly = mode == "always_stocked" and (bought is None or (today - bought).days >= MONTHLY_CHECK_DAYS)
            info = tuple(sorted((f, {"source": s, "revision": pol.revisions[s]}) for f, s in pol.sources.items())) + ((("stocking", mode),) if mode != "standard" else ())      # FR-004: scope, key and revision
            level = pol.values.service_level if pol.values.service_level is not None else Decimal(str(v["service_level"]))
            out.append(VariantInput(vid, int(pid), int(v.get("on_hand", 0)), forecast, level, tuple(offers),
                                    tuple(inbound.get(vid, ())), expiring, bool(v.get("clinical_critical")), soon,
                                    overrides.get((vid, "safety_stock")), overrides.get((vid, "min"), pol.values.min_units),
                                    overrides.get((vid, "max"), pol.values.max_units), floor if mode == "always_stocked" else 0, monthly, info))
            if pol.values.safety_stock_units is not None and (vid, "safety_stock") not in overrides:
                out[-1] = replace(out[-1], safety_override=pol.values.safety_stock_units)
        terms: dict[str, SupplierTermsIn] = {}
        versions_used: dict[str, Any] = {}
        for sid in sorted(used_suppliers):
            row = current_row(conn, sid, now)
            t = None if row is None else row_to_terms(row)
            terms[sid] = SupplierTermsIn(sid) if t is None else SupplierTermsIn(
                sid, t.min_order_value, t.min_qty_for_delivery, t.free_delivery_threshold, t.delivery_charge, t.discounts, t.preferred, t.disabled, int(row.version),
                next_order_date=order_date_from(now, t.order_days, t.order_cutoff_time) if t.order_days or t.order_cutoff_time else None,   # MMI-6 FR-020
                delivery_weekdays=t.delivery_weekdays)
            versions_used[sid] = {"supplier": None if row is None else int(row.version), "overrides": overrides_used.get(sid, {})}
        self.report = report
        capped, capped_by = effective_weekly_budget_with_source(conn, today)
        policy_versions.update(budget_versions(conn, today))
        return ProposalInputs(today, tuple(out), terms, capped if capped is not None else self.budget, terms_versions=versions_used, policy_versions=policy_versions,
                              forecast_run_id=fc.get("run_id"), dataset_version_id=fc.get("dataset_version_id"),
                              budget_source=capped_by, supplier_budgets=supplier_weekly_budgets(conn, today), defer_for_cap=True)
