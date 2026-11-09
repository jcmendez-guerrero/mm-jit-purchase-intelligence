"""T055: a seed file is the owner's own estimate, never an ERP export (those are local-only under the constitution).

Recognises the three ERP UI export layouts by a few distinctive headers. Two or more hits from one layout is enough; the seed template shares none of them.
"""

from __future__ import annotations

import unicodedata


def _fold(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


# Distinctive headers only ("Referencia" is left out: it is a legitimate synonym for SKU in the seed mapping).
_SHAPES = {
    "inventory": {_fold(h) for h in ("Stock Disponible", "Stock Reservado", "Stock Total", "Precio Coste (€)", "Punto de Reorden", "Stock Objetivo")},
    "movements": {_fold(h) for h in ("Motivo", "Caducidad", "Ubicación", "Lote")},
    "suppliers": {_fold(h) for h in ("CIF", "IBAN", "SWIFT", "Nombre Empresa", "Condiciones Pago", "Tipo Fiscal")},
}


def erp_export_shape(headers: list[str]) -> str | None:
    """The layout name when the headers look like an ERP export, else None."""
    have = {_fold(h) for h in headers}
    for name, distinctive in _SHAPES.items():
        if len(have & distinctive) >= 2:
            return name
    return None
