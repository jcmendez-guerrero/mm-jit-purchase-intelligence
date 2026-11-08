"""Shared helpers for the scenario tests: a small catalogue with two suppliers, built from the proposal-engine builders."""

from decimal import Decimal

from builders import flat_forecast, inputs, offer, terms, variant
from conftest import add_supplier

D = Decimal


def suppliers(conn):
    return add_supplier(conn, 1, "Proveedor A"), add_supplier(conn, 2, "Proveedor B")


def base(sa, sb, a_min="25", critical=False, budget=None, n=3, a_free=None, a_charge=None):
    """n variants, each offered by A at 1.00 and B at 1.20. A has a minimum order value, B none."""
    vs = [variant(i, [offer(sa, "1.00", pack=1, lead=3), offer(sb, "1.20", pack=1, lead=3)], flat_forecast(1.0), critical=critical and i == 1) for i in range(1, n + 1)]
    return inputs(vs, [terms(sa, min_value=a_min, free=a_free, charge=a_charge), terms(sb)], budget=budget)


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()
