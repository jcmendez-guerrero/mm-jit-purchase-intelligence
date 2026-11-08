"""Builders for proposal-engine tests."""

import math
from datetime import date
from decimal import Decimal

from proposals.model import Forecast, HorizonForecast, Offer, ProposalInputs, SupplierTermsIn, VariantInput

D = Decimal
TODAY = date(2026, 11, 9)
HORIZONS = (7, 14, 21, 28, 42)


def linear_forecast(rate=1.0, k=2.0, policy="minmax_poisson"):
    """Eligible forecast: mean = rate*h, every service-level quantile = ceil(mean + k*sqrt(mean))."""
    hs = {}
    for h in HORIZONS:
        mean = rate * h
        q = math.ceil(mean + k * math.sqrt(mean))
        hs[h] = HorizonForecast(mean, {lv: q for lv in ("0.85", "0.90", "0.95", "0.97", "0.99")})
    return Forecast(hs, policy, True)


def flat_forecast(per_day_q=2.0, policy="minmax_poisson"):
    """q(h) = per_day_q*h exactly, easy to reason about when interpolating."""
    hs = {h: HorizonForecast(per_day_q * h / 2, {lv: int(per_day_q * h) for lv in ("0.85", "0.90", "0.95", "0.97", "0.99")}) for h in HORIZONS}
    return Forecast(hs, policy, True)


def fallback_forecast(min_=3, max_=9):
    return Forecast({h: HorizonForecast(None, {"min": min_ * h // 7, "max": max_ * h // 7}) for h in HORIZONS}, "minmax_conservative", False, ("too_sparse",))


def offer(supplier, cost, pack=1, lead=3, moq=0, status="ok", source="siweb_product_supplier"):
    return Offer(supplier, D(cost), f"cost-{supplier}", source, status, pack, lead, moq)


def variant(vid, offers, forecast=None, on_hand=0, level="0.95", inbound=(), expiring=0, critical=False, soon=0):
    return VariantInput(vid, vid * 10, on_hand, forecast or flat_forecast(), D(level), tuple(offers), tuple(inbound), expiring, critical, soon)


def terms(sid, min_value=None, min_qty=None, free=None, charge=None):
    f = lambda v: None if v is None else D(v)  # noqa: E731
    return SupplierTermsIn(sid, f(min_value), min_qty, f(free), f(charge))


def inputs(variants, suppliers=(), budget=None, overrides=None, **kw):
    from proposals.model import Overrides

    return ProposalInputs(TODAY, tuple(variants), {t.supplier_id: t for t in suppliers}, None if budget is None else D(budget), overrides or Overrides(), **kw)


class FakeLots:
    """Stands in for the inventory lots lookup: ``items`` are {variant_id, lot, quantity}; ``fail`` makes the next N calls raise."""

    def __init__(self, items, fail=0):
        self.items, self.fail, self.calls = list(items), fail, 0

    def in_stock(self, variant_ids):
        self.calls += 1
        if self.fail:
            self.fail -= 1
            raise ConnectionError("inventory down")
        return [i for i in self.items if i["variant_id"] in variant_ids]
