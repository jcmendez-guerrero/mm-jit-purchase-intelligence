"""T019: synthetic files in the shape of the three Siweb UI exports (inventory CSV, movements XLSX, suppliers CSV).

Everything is fictional and visibly synthetic (``SYN-`` SKUs, supplier ids in the reserved synthetic range, ``.invalid``
e-mail domains). The shape (columns, formats, quirks) mirrors what the owner's real exports look like; no value is copied.
The output is byte-for-byte reproducible for a given seed.
"""

from __future__ import annotations

import csv
import io
import random
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import openpyxl
from export_loader import formats

CENT = Decimal("0.01")
WAREHOUSES = ["Almacen Sintetico 1", "Almacen Sintetico 2", "Almacen Sintetico 3"]
CATEGORIES = ["Alimentacion Sintetica", "Higiene Sintetica", "Farmacia Sintetica", "Accesorios Sintetica", "Juguetes Sinteticos", "Servicios Sinteticos"]
BRANDS = ["Marca Sintetica A", "Marca Sintetica B", "Marca Sintetica C", "Marca Sintetica D", "Marca Sintetica E"]
DUP_A = "Distribuciones Sinteticas Norte S.L."
DUP_B = "DISTRIBUCIONES SINTÉTICAS NORTE SL"
PAYMENT_TERMS = ["7 días", "30", "", "a convenir", "30 días", "60"]
FIRST_SYNTHETIC_SUPPLIER = formats.SYNTHETIC_SUPPLIER_IDS.start + 1


@dataclass
class ExportSet:
    inventory: list[dict[str, str]]
    movements: list[dict[str, Any]]
    suppliers: list[dict[str, str]]
    truth: dict[str, int] = field(default_factory=dict)


def _money(x: Decimal) -> str:
    return str(x.quantize(CENT, rounding=ROUND_HALF_UP))


def _supplier_rows(rng: random.Random, n: int, truth: dict[str, int]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i in range(n):
        ident = FIRST_SYNTHETIC_SUPPLIER + i
        row = dict.fromkeys(formats.SUPPLIERS_HEADERS, "")
        name = f"Proveedor Sintetico {i + 1:02d} S.L."
        fiscal, country, currency, relation = "nacional", "España", "EUR", "Proveedor"
        if i == 0:
            name = DUP_A
        elif i == 1:
            name = DUP_B
        elif i in (2, 3, 4):
            name, relation = f"Cliente Sintetico {i - 1:02d}", "Cliente"
        elif i == 5:
            name, fiscal, country, currency = "Proveedor Sintetico Extranjero 01 Ltd", "extranjero", "Estados Unidos", "USD"
        elif i == 6:
            name, fiscal, country = "Proveedor Sintetico Comunitario 01 Ltd", "intracomunitario", "Irlanda"
        row.update({
            "ID": str(ident), "Nombre Empresa": name, "CIF": "" if i % 7 == 3 else f"XSYN{rng.randint(0, 99999):05d}Z", "Tipo Fiscal": fiscal,
            "Dirección": f"Calle Sintetica {i + 1}", "Ciudad": "Ciudad Sintetica", "Provincia": "Provincia Sintetica",
            "Código Postal": f"{rng.randint(1000, 52999):05d}", "País": country, "Teléfono Principal": "" if i % 3 else f"+34 900 000 {i:03d}",
            "Email General": "" if i % 2 else f"info{i + 1}@proveedor-sintetico.invalid", "Tipo Relación": relation,
            "Condiciones Pago": PAYMENT_TERMS[i % len(PAYMENT_TERMS)] if relation == "Proveedor" else "",
            "Moneda Habitual": currency, "Notas": "Nota sintetica con texto libre" if i == 8 else "",
            "Fecha Alta": f"2026-0{1 + i % 9}-{1 + i % 27:02d}", "Fecha Creación": f"2026-0{1 + i % 9}-{1 + i % 27:02d}T08:00:00.000000",
            "Fecha Actualización": f"2026-0{1 + i % 9}-{1 + i % 27:02d}T08:00:01.000000",
        })
        if i == 9:   # a payment term that cannot be turned into days
            row["Condiciones Pago"] = "a convenir"
        if i == 10:
            row["Condiciones Pago"] = "7 días"
        rows.append(row)
    truth["customer_rows"] = sum(r["Tipo Relación"] == "Cliente" for r in rows)
    return rows


def _inventory_rows(rng: random.Random, n: int, suppliers: list[dict[str, str]], truth: dict[str, int]) -> list[dict[str, str]]:
    regular = [r["Nombre Empresa"] for r in suppliers if r["Tipo Relación"] == "Proveedor" and r["Nombre Empresa"] not in (DUP_A, DUP_B)]
    rows: list[dict[str, str]] = []
    for i in range(n):
        service = i >= n - 3
        sale = Decimal(rng.randint(150, 9000)) / 100
        cost = sale * Decimal(rng.randint(40, 75)) / 100
        kind = rng.choice([("IVA", 10), ("IVA10", 10), ("IVA10", 10), ("IVA21", 21), ("IVA", 21)])
        available = rng.choice([0, 0, 1, 2, 3, 4, 6, 8, 12])
        reserved = rng.choice([0, 0, 0, 1]) if available else 0
        lot = f"LOT-{rng.randint(1, 99999):05d}" if rng.random() < 0.16 else ""
        supplier = ""
        r = rng.random()
        if r < 0.12:
            supplier = rng.choice(regular)
        elif r < 0.14:
            supplier = DUP_A.replace(".", "").upper()           # matches two suppliers once folded: ambiguous
        elif r < 0.16:
            supplier = "Proveedor Inexistente Sintetico"
        row = {
            "SKU": f"SYN-{i + 1:06d}", "Nombre": f"Producto Sintetico {i + 1:04d}",
            "Descripción": f"Descripcion sintetica {i + 1}" + ("\nSegunda linea sintetica" if i % 5 == 0 else ""),
            "Categoría": CATEGORIES[-1] if service else CATEGORIES[i % (len(CATEGORIES) - 1)], "Marca": BRANDS[i % len(BRANDS)],
            "Proveedor": supplier, "Tipo": "Servicio" if service else "Físico", "Unidad de Medida": "hora" if service else "unidad",
            "Categoría Unidad": "time" if service else "count", "Precio Venta (€)": _money(sale), "Precio Coste (€)": _money(cost),
            "Tipo Impuesto": kind[0], "Tasa Impuesto (%)": str(kind[1]), "Impuesto Incluido": "Sí" if rng.random() < 0.08 else "No",
            "Stock Disponible": str(available), "Stock Reservado": str(reserved), "Stock Total": str(available + reserved),
            "Punto de Reorden": str(rng.choice([0, 1, 2, 3, 5])), "Stock Objetivo": str(rng.choice([0, 2, 4, 6, 12])),
            "Moneda": "EUR", "Estado": "Activo", "Lote": lot,
        }
        rows.append(row)
    # planted quirks at fixed positions
    rows[5].update({"Stock Disponible": "0", "Stock Reservado": "5", "Stock Total": "2"})
    rows[6].update({"Stock Disponible": "-3", "Stock Reservado": "0", "Stock Total": "-3"})
    rows[7]["Precio Coste (€)"] = "0.00"
    rows[8].update({"Precio Venta (€)": "12.00", "Precio Coste (€)": "20.00"})
    rows[9]["Moneda"] = "USD"
    rows[10]["Estado"] = "Inactivo"
    dup = dict(rows[11])                                          # same SKU, second lot
    dup.update({"Lote": "LOT-77777", "Stock Disponible": "2", "Stock Reservado": "0", "Stock Total": "2"})
    rows.append(dup)
    truth["service_rows"] = sum(r["Tipo"] == "Servicio" for r in rows)
    truth["repeated_sku_rows"] = 1
    return rows


def _movement_rows(rng: random.Random, inventory: list[dict[str, str]], n: int, end: date, truth: dict[str, int]) -> list[dict[str, Any]]:
    physical = [r["SKU"] for r in inventory if r["Tipo"] == "Físico"]
    names = {r["SKU"]: r["Nombre"] for r in inventory}
    start = date(2026, 7, 1)
    span = (end - start).days
    kinds = (
        [("Salida", "Envío de venta", -1)] * 35 + [("Entrada", "Recepción de compra", 1)] * 35 + [("Ajuste", "Ajuste negativo", -1)] * 8
        + [("Ajuste", "Ajuste positivo", 1)] * 4 + [("Entrada", "Devolución de cliente", 1)] * 3 + [("Entrada", "Stock inicial", 1)] * 6
        + [("Transferencia", "Salida por transferencia", -1)] * 4 + [("Transferencia", "Entrada por transferencia", 1)] * 4
    )
    rows: list[dict[str, Any]] = []
    ticket = purchase = 0
    # one of every mapped pair first, so every mapping is exercised whatever the seed
    plan = sorted(set(kinds)) + [rng.choice(kinds) for _ in range(n - 8 - 8)]
    for tipo, motivo, sign in plan:
        sku = rng.choice(physical)
        when = datetime.combine(start + timedelta(days=rng.randint(0, span)), datetime.min.time()) + timedelta(hours=rng.randint(8, 19), minutes=rng.randint(0, 59))
        qty = sign * (1 if rng.random() < 0.85 else rng.randint(2, 6))
        lot = expiry = reference = note = ""
        if motivo == "Recepción de compra":
            purchase += 1
            reference, note = f"Compra #{purchase}", ""
            if rng.random() < 0.92:
                lot = f"LOT-{rng.randint(1, 99999):05d}"
                if rng.random() < 0.75:
                    expiry = (when.date() + timedelta(days=rng.randint(120, 900))).strftime("%d/%m/%Y")
        elif motivo == "Envío de venta":
            ticket += 1
            reference = f"SYN-2026-{ticket:06d}"
            note = f"Venta - Ticket {reference}"
            if rng.random() < 0.7:
                lot = f"LOT-{rng.randint(1, 99999):05d}"
        elif motivo.startswith("Ajuste"):
            note = "Ajuste sintetico"
        rows.append({"when": when, "Producto": names[sku], "SKU": sku, "Almacén": rng.choice(WAREHOUSES), "Ubicación": "", "Lote": lot,
                     "Caducidad": expiry, "Tipo": tipo, "Motivo": motivo, "Cantidad": qty, "Notas": note, "Referencia": reference})
    base = rows[0]
    planted: list[dict[str, Any]] = [
        {**base, "SKU": "SYN-999001", "Producto": "Producto Sintetico Desconocido", "Tipo": "Salida", "Motivo": "Envío de venta", "Cantidad": -1, "Caducidad": ""},
        {**base, "SKU": "SYN-999002", "Producto": "Producto Sintetico Desconocido", "Tipo": "Salida", "Motivo": "Envío de venta", "Cantidad": -1, "Caducidad": ""},
        {**rows[1], "Tipo": "Entrada", "Motivo": "Recepción de compra", "Cantidad": 6, "Lote": "LOT-00001", "Caducidad": "30/08/027"},
        {**rows[2], "Tipo": "Entrada", "Motivo": "Recepción de compra", "Cantidad": 6, "Lote": "LOT-00002", "Caducidad": "30/08/028"},
        {**rows[3], "Tipo": "Salida", "Motivo": "Rotura sintetica", "Cantidad": -1, "Caducidad": ""},
        {**rows[4], "Tipo": "Salida", "Motivo": "Merma sintetica", "Cantidad": -1, "Caducidad": ""},
        {**rows[5], "Tipo": "Salida", "Motivo": "Envío de venta", "Cantidad": 2, "Caducidad": ""},        # sign does not match the reason
        {**rows[6], "Tipo": "Salida", "Motivo": "Envío de venta", "Cantidad": -1, "Lote": "", "Caducidad": ""},
    ]
    rows.extend(planted)
    rows.sort(key=lambda r: r["when"], reverse=True)               # newest first, like the real export
    truth.update({"unknown_sku_rows": 2, "bad_expiry_rows": 2, "unmapped_reason_rows": 2, "sign_mismatch_rows": 1})
    return rows


def generate_exports(seed: int = 42, n_products: int = 300, n_movements: int = 400, n_suppliers: int = 25, end: date = date(2026, 10, 31)) -> ExportSet:
    rng = random.Random(seed)
    truth: dict[str, int] = {}
    suppliers = _supplier_rows(rng, n_suppliers, truth)
    inventory = _inventory_rows(rng, n_products, suppliers, truth)
    movements = _movement_rows(rng, inventory, n_movements, end, truth)
    return ExportSet(inventory, movements, suppliers, truth)


def _csv_bytes(headers: list[str], rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(rows)
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def _normalise_zip(data: bytes) -> bytes:
    """Fixed timestamps and entry order so the workbook bytes depend only on the content."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for name in sorted(src.namelist()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, src.read(name))
    return out.getvalue()


def _xlsx_bytes(movements: list[dict[str, Any]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append(formats.MOVEMENTS_HEADERS)
    for m in movements:
        ws.append([m["when"].strftime("%d/%m/%Y, %H:%M"), m["Producto"], m["SKU"], m["Almacén"], m["Ubicación"], m["Lote"], m["Caducidad"],
                   m["Tipo"], m["Motivo"], m["Cantidad"], m["Notas"], m["Referencia"]])
    wb.properties.creator = "synthetic"
    wb.properties.created = wb.properties.modified = datetime(2026, 1, 1)  # noqa: DTZ001 - fixed, naive on purpose (reproducible bytes)
    buf = io.BytesIO()
    wb.save(buf)
    return _normalise_zip(buf.getvalue())


def write_exports(out_dir: Path, seed: int = 42, **kwargs: Any) -> ExportSet:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = generate_exports(seed=seed, **kwargs)
    (out / "inventario.csv").write_bytes(_csv_bytes(formats.INVENTORY_HEADERS, data.inventory))
    (out / "movimientos.xlsx").write_bytes(_xlsx_bytes(data.movements))
    (out / "proveedores.csv").write_bytes(_csv_bytes(formats.SUPPLIERS_HEADERS, data.suppliers))
    return data


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Write synthetic export-shaped files")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    write_exports(Path(a.out), seed=a.seed)
