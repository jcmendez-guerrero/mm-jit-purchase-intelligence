"""T029: inventory CSV → products by SKU, stock and lots, with every row accounted for (SC-002).

Free-text descriptions are never kept. Rows that cannot be trusted are quarantined into the loader's review list (source
``loader``); odd-but-usable rows (reserved above total, negative stock, zero cost, cost above price) load and are flagged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .formats import LOCAL_TIMEZONE, fold
from .readers import read_table
from .report import LoadReport
from .validate_file import Limits
from .values import CENT, parse_decimal, parse_flag, parse_int


def sku_key(sku: str) -> str:
    return sku.strip().casefold()


@dataclass
class InventoryItem:
    sku: str
    name: str
    category: str
    brand: str
    supplier_name: str
    kind: str                      # physical / service
    uom: str
    uom_category: str
    price: Decimal
    cost: Decimal | None
    tax_kind: str
    tax_rate: Decimal | None
    tax_included: bool
    pvp_gross: Decimal
    currency: str
    status: str                    # active / inactive
    available: int = 0
    reserved: int = 0
    total: int = 0
    reorder_point: int = 0
    target_stock: int = 0
    lots: list[tuple[str, int]] = field(default_factory=list)   # (batch, quantity)
    rows: list[int] = field(default_factory=list)


@dataclass
class InventoryParse:
    items: dict[str, InventoryItem]
    report: LoadReport
    ok_rows: int = 0


def _gross(price: Decimal, rate: Decimal | None, included: bool) -> Decimal:
    if included or not rate:
        return price.quantize(CENT, rounding=ROUND_HALF_UP)
    return (price * (Decimal(1) + rate / 100)).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_inventory(data: bytes, filename: str, limits: Limits) -> InventoryParse:
    rows = read_table("inventory", filename, data, limits)
    report = LoadReport(kind="inventory", file_sha256=hashlib.sha256(data).hexdigest(), rows=len(rows))
    out = InventoryParse({}, report)
    included_rows = excluded_rows = 0

    def quarantine(n: int, code: str, detail: str = "") -> None:
        report.quarantined += 1
        report.review(n, code, detail)

    for n, r in enumerate(rows, start=2):
        sku = r["SKU"].strip()
        if not sku:
            quarantine(n, "missing_sku", "Fila sin SKU")
            continue
        if len(sku) > 60:
            quarantine(n, "sku_too_long", "SKU de más de 60 caracteres")
            continue
        kind_f = fold(r["Tipo"])
        kind = {"fisico": "physical", "servicio": "service"}.get(kind_f)
        if kind is None:
            quarantine(n, "unknown_type", "Tipo de artículo no reconocido")
            continue
        if r["Moneda"].strip().upper() not in {"EUR", ""}:
            quarantine(n, "currency_not_eur", "Moneda distinta de EUR")
            continue
        try:
            price = parse_decimal(r["Precio Venta (€)"]) if r["Precio Venta (€)"] else Decimal(0)
            cost = parse_decimal(r["Precio Coste (€)"]) if r["Precio Coste (€)"] else None
            rate = parse_decimal(r["Tasa Impuesto (%)"]) if r["Tasa Impuesto (%)"] else None
            available = parse_int(r["Stock Disponible"] or "0")
            reserved = parse_int(r["Stock Reservado"] or "0")
            total = parse_int(r["Stock Total"] or "0")
            reorder = parse_int(r["Punto de Reorden"] or "0")
            target = parse_int(r["Stock Objetivo"] or "0")
        except ValueError:
            quarantine(n, "invalid_number", "Valor numérico no válido")
            continue
        if price < 0 or (cost is not None and cost < 0) or reorder < 0 or target < 0:
            quarantine(n, "negative_amount", "Importe negativo")
            continue
        included = parse_flag(r["Impuesto Incluido"])
        if included is None:
            quarantine(n, "unknown_tax_flag", "Indicador de impuesto incluido no reconocido")
            continue

        key = sku_key(sku)
        if kind == "service":
            report.services += 1
            out.items.setdefault(key, InventoryItem(
                sku=sku, name=r["Nombre"], category=r["Categoría"], brand=r["Marca"], supplier_name=r["Proveedor"], kind=kind,
                uom=r["Unidad de Medida"], uom_category=r["Categoría Unidad"], price=price, cost=cost, tax_kind=r["Tipo Impuesto"],
                tax_rate=rate, tax_included=included, pvp_gross=_gross(price, rate, included), currency="EUR",
                status="active" if fold(r["Estado"]) == "activo" else "inactive", rows=[n],
            ))
            continue

        out.ok_rows += 1
        included_rows += included
        excluded_rows += not included
        lot = r["Lote"].strip()
        item = out.items.get(key)
        if item is None:
            item = out.items[key] = InventoryItem(
                sku=sku, name=r["Nombre"], category=r["Categoría"], brand=r["Marca"], supplier_name=r["Proveedor"], kind=kind,
                uom=r["Unidad de Medida"] or "unidad", uom_category=r["Categoría Unidad"] or "count", price=price, cost=cost,
                tax_kind=r["Tipo Impuesto"], tax_rate=rate, tax_included=included, pvp_gross=_gross(price, rate, included),
                currency="EUR", status="active" if fold(r["Estado"]) == "activo" else "inactive",
                reorder_point=reorder, target_stock=target,
            )
        else:
            if item.price != price:
                report.review(n, "conflicting_price", "Precio distinto al de otra fila del mismo SKU")
            if item.cost != cost:
                report.review(n, "conflicting_cost", "Coste distinto al de otra fila del mismo SKU")
        item.rows.append(n)
        item.available += available
        item.reserved += reserved
        item.total += total
        if lot:
            item.lots.append((lot, total))
        if reserved > total:
            report.review(n, "reserved_above_total", "Reservado mayor que el total")
        if total < 0:
            report.review(n, "negative_stock", "Stock total negativo")
        if cost is not None and cost == 0:
            report.review(n, "zero_cost", "Coste cero")
        if cost is not None and price > 0 and cost > price:
            report.review(n, "cost_above_price", "Coste superior al precio de venta")
    report.interpretations = {"tax_included_rows": included_rows, "tax_excluded_rows": excluded_rows, "timezone": LOCAL_TIMEZONE}
    return out
