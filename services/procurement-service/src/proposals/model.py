"""Inputs and outputs of proposal generation. Plain immutable data: the engine is a pure function of ProposalInputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

RULES_VERSION = "1.0.0"
TICKS = 10_000                    # integer money unit: 1/10000 EUR, so no float ever touches a cost
DEFAULT_LEAD_DAYS = 7
REVIEW_DAYS = 7                   # the weekly review period: protection horizon = review + supplier lead time


def ticks(amount: Decimal) -> int:
    return int((amount * TICKS).to_integral_value(rounding="ROUND_HALF_UP"))


def money(t: int) -> Decimal:
    return Decimal(t) / TICKS


@dataclass(frozen=True)
class HorizonForecast:
    mean: float | None
    quantiles: dict[str, int]


@dataclass(frozen=True)
class Forecast:
    horizons: dict[int, HorizonForecast]
    policy: str
    eligible: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Offer:
    supplier_id: str
    unit_cost: Decimal                 # with recargo
    cost_id: str | None = None
    source: str = "manual"
    cost_status: str = "ok"            # ok / stale (blocked costs never become offers)
    pack_size: int = 1
    lead_time_days: int = DEFAULT_LEAD_DAYS
    min_order_qty: int = 0


@dataclass(frozen=True)
class VariantInput:
    variant_id: int
    product_id: int
    on_hand: int
    forecast: Forecast
    service_level: Decimal
    offers: tuple[Offer, ...]
    inbound: tuple[tuple[int, int], ...] = ()      # (qty, days until arrival)
    expiring_qty: int = 0                         # units that expire before the end of the horizon
    clinical_critical: bool = False
    soon_need: int = 0                            # units needed in the following review period (top-up candidate)


@dataclass(frozen=True)
class SupplierTermsIn:
    supplier_id: str
    min_order_value: Decimal | None = None
    min_qty_for_delivery: int | None = None
    free_delivery_threshold: Decimal | None = None
    delivery_charge: Decimal | None = None


@dataclass(frozen=True)
class Overrides:
    fixed_supplier: dict[int, str] = field(default_factory=dict)       # variant_id -> supplier_id
    fixed_qty: dict[int, int] = field(default_factory=dict)            # variant_id -> units
    excluded: dict[int, frozenset[str]] = field(default_factory=dict)  # variant_id -> suppliers not to use


@dataclass(frozen=True)
class ProposalInputs:
    today: date
    variants: tuple[VariantInput, ...]
    suppliers: dict[str, SupplierTermsIn]
    budget: Decimal | None = None
    overrides: Overrides = field(default_factory=Overrides)
    max_lead_days: int = 21
    risk_penalty_ticks_per_unit_day: int = 100         # 0.01 EUR per unit per extra day of lead time


def canonical(obj: Any) -> str:
    def default(o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        if hasattr(o, "__dataclass_fields__"):
            return {k: getattr(o, k) for k in o.__dataclass_fields__}
        raise TypeError(type(o))

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=default)


def inputs_hash(inputs: ProposalInputs, rule_versions: dict[str, str]) -> str:
    return hashlib.sha256((canonical(inputs) + canonical(rule_versions)).encode()).hexdigest()
