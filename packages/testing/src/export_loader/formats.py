"""Layouts and vocabularies of the three Siweb UI exports (specs/004-local-test-data-suppliers/contracts/export-formats.md).

``scripts/check_export_signatures.py`` keeps its own copy of the header lists (it must run without installing the
project); a test asserts both copies are identical.
"""

from __future__ import annotations

import unicodedata

INVENTORY_HEADERS = [
    "SKU", "Nombre", "Descripción", "Categoría", "Marca", "Proveedor", "Tipo", "Unidad de Medida", "Categoría Unidad",
    "Precio Venta (€)", "Precio Coste (€)", "Tipo Impuesto", "Tasa Impuesto (%)", "Impuesto Incluido", "Stock Disponible",
    "Stock Reservado", "Stock Total", "Punto de Reorden", "Stock Objetivo", "Moneda", "Estado", "Lote",
]
MOVEMENTS_HEADERS = ["Fecha", "Producto", "SKU", "Almacén", "Ubicación", "Lote", "Caducidad", "Tipo", "Motivo", "Cantidad", "Notas", "Referencia"]
SUPPLIERS_HEADERS = [
    "ID", "Nombre Empresa", "CIF", "Tipo Fiscal", "Sector", "Dirección", "Ciudad", "Provincia", "Código Postal", "País",
    "Teléfono Principal", "Email General", "Página Web", "Nombre Contacto", "Apellidos Contacto", "Cargo", "Teléfono Directo",
    "Email Directo", "LinkedIn", "Tipo Relación", "Categoría", "Fecha Alta", "Último Contacto", "Condiciones Pago", "Métodos Pago",
    "Moneda Habitual", "Email Empresa", "Email Personal", "Teléfono Emergencia", "Notas", "Nombre Facturación",
    "Dirección Facturación", "Ciudad Facturación", "Código Postal Facturación", "Provincia Facturación", "País Facturación",
    "Banco", "IBAN", "SWIFT", "Fecha Creación", "Fecha Actualización",
]
HEADERS = {"inventory": INVENTORY_HEADERS, "movements": MOVEMENTS_HEADERS, "suppliers": SUPPLIERS_HEADERS}

SURROGATE_BASE = 9_000_000          # reserved range for ids assigned to locally loaded SKUs (never sent to the ERP)
SYNTHETIC_PREFIX = "SYN-"
SYNTHETIC_SUPPLIER_IDS = range(9_100_000, 9_200_000)
LOCAL_TIMEZONE = "Europe/Madrid"


def fold(text: str) -> str:
    """Lower-case, accent-folded, whitespace-collapsed text used for matching (never for display)."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


# (Tipo, Motivo) as exported → platform movement reason. Keys are folded. Anything else goes to the review list.
REASON_MAP: dict[tuple[str, str], str] = {
    (fold("Entrada"), fold("Recepción de compra")): "purchase_receipt",
    (fold("Salida"), fold("Envío de venta")): "sale_shipment",
    (fold("Entrada"), fold("Devolución de cliente")): "return_customer",
    (fold("Ajuste"), fold("Ajuste negativo")): "adjustment_negative",
    (fold("Ajuste"), fold("Ajuste positivo")): "adjustment_positive",
    (fold("Entrada"), fold("Stock inicial")): "initial_stock",
    (fold("Transferencia"), fold("Entrada por transferencia")): "transfer_in",
    (fold("Transferencia"), fold("Salida por transferencia")): "transfer_out",
}
# Reasons whose quantity sign is fixed by their meaning; a mismatch goes to review.
POSITIVE_REASONS = {"purchase_receipt", "return_customer", "adjustment_positive", "initial_stock", "transfer_in"}
NEGATIVE_REASONS = {"sale_shipment", "adjustment_negative", "transfer_out"}

COUNTRY_ISO = {
    fold(k): v for k, v in {
        "España": "ES", "Spain": "ES", "Portugal": "PT", "Francia": "FR", "France": "FR", "Italia": "IT", "Italy": "IT",
        "Irlanda": "IE", "Ireland": "IE", "Chipre": "CY", "Cyprus": "CY", "Alemania": "DE", "Germany": "DE",
        "Reino Unido": "GB", "United Kingdom": "GB", "Estados Unidos": "US", "United States": "US", "China": "CN",
    }.items()
}
FISCAL_TYPE = {fold("nacional"): "national", fold("intracomunitario"): "intracommunity", fold("extranjero"): "foreign"}
