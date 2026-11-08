"""The guard script keeps its own copy of the header lists; both copies must match."""

import importlib.util
import sys
from pathlib import Path

from export_loader import formats

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "check_export_signatures.py"


def test_guard_script_headers_match_formats():
    spec = importlib.util.spec_from_file_location("guard_script", SCRIPT)
    guard = importlib.util.module_from_spec(spec)
    sys.modules["guard_script"] = guard
    spec.loader.exec_module(guard)
    assert guard.INVENTORY == formats.INVENTORY_HEADERS
    assert guard.MOVEMENTS == formats.MOVEMENTS_HEADERS
    assert guard.SUPPLIERS == formats.SUPPLIERS_HEADERS
    assert guard.SYNTHETIC_PREFIX == formats.SYNTHETIC_PREFIX
    assert guard.SYNTHETIC_SUPPLIER_IDS == formats.SYNTHETIC_SUPPLIER_IDS


def test_fold_removes_accents_and_case():
    assert formats.fold("  Envío  DE   Venta ") == "envio de venta"


def test_reason_map_covers_the_eight_seen_pairs():
    assert len(formats.REASON_MAP) == 8
    assert formats.REASON_MAP[(formats.fold("Salida"), formats.fold("Envío de venta"))] == "sale_shipment"
